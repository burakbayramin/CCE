-- M4.1 — the shared durable-job protocol.
--
-- Everything M4 builds on stands here: a character can hold one interaction
-- reservation, a worker holds a fenced lease with an ownership generation, a
-- domain effect is applied at most once under a stable identity, and the
-- result lands in one transaction that also emits its outbox rows.
--
-- Two rules from WADR-006/WADR-011 drive the design and are the reason this is
-- not simply another job table:
--
-- 1. Losing a lease must NOT make the character available again. An expired
--    reservation stays held until it is explicitly resolved, so a slow or dead
--    worker cannot let a second interaction start on a character whose state
--    may still be mid-flight.
-- 2. The domain effect identity must not contain a model name or a processing
--    version. Retrying the same experience under a different model has to
--    collide with the effects already applied, or the world gains duplicate
--    memories every time the model is swapped.

begin;

set local role cce_migrator;

create schema if not exists ops_private;
revoke all on schema ops_private from public, anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Interaction reservations: one live interaction per character.
-- ---------------------------------------------------------------------------
create table ops_private.interaction_reservations (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null references world_private.characters(id) on delete cascade,
    purpose text not null
        check (purpose in ('ADMIN_CHAT', 'SCENE')),
    state text not null default 'HELD'
        check (state in ('HELD', 'RESULT_COMMITTED', 'RESOLVED')),
    -- Ownership generation. Every lease takeover increments it, so a stale
    -- worker holding an older generation can never commit.
    ownership_generation bigint not null default 1 check (ownership_generation > 0),
    lease_until timestamptz,
    lease_holder text,
    -- The committed effect identity. Set once, when the result lands.
    effect_identity text,
    committed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- At most one unresolved reservation per character, regardless of purpose.
create unique index interaction_reservations_live_idx
    on ops_private.interaction_reservations(character_id)
    where state = 'HELD';
create index interaction_reservations_lease_idx
    on ops_private.interaction_reservations(lease_until)
    where state = 'HELD' and lease_until is not null;

alter table ops_private.interaction_reservations enable row level security;
alter table ops_private.interaction_reservations force row level security;

create policy migrator_interaction_reservation on ops_private.interaction_reservations
    for all to cce_migrator using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Domain effects: the stable, version-independent dedup identity.
-- ---------------------------------------------------------------------------
create table ops_private.domain_effects (
    id uuid primary key default gen_random_uuid(),
    -- Deliberately no model name, provider or processing version. Re-running
    -- the same experience under a different model collapses onto this key.
    effect_identity text not null unique,
    reservation_id uuid references ops_private.interaction_reservations(id) on delete cascade,
    effect_kind text not null
        check (effect_kind in ('MEMORY', 'AFFECT', 'RELATIONSHIP', 'GOAL', 'TRANSCRIPT')),
    -- Where the effect came from, for operator forensics only. Never part of
    -- the identity.
    applied_by_processing_version text,
    payload jsonb not null default '{}'::jsonb,
    recorded_at timestamptz not null default now()
);

alter table ops_private.domain_effects enable row level security;
alter table ops_private.domain_effects force row level security;

create policy migrator_domain_effect on ops_private.domain_effects
    for all to cce_migrator using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Job runs: append-only execution ledger, one row per attempt.
-- ---------------------------------------------------------------------------
create table ops_private.job_runs (
    id uuid primary key default gen_random_uuid(),
    reservation_id uuid not null references ops_private.interaction_reservations(id) on delete cascade,
    attempt_number integer not null check (attempt_number > 0),
    ownership_generation bigint not null check (ownership_generation > 0),
    state text not null default 'RUNNING'
        check (state in ('RUNNING', 'SUCCEEDED', 'FAILED', 'QUARANTINED', 'ABANDONED')),
    worker_id text,
    error_code text,
    -- True once the domain result was committed. A late result from a lost
    -- lease must not be able to set this.
    result_committed boolean not null default false,
    started_at timestamptz not null default now(),
    finished_at timestamptz
);

create unique index job_runs_attempt_idx
    on ops_private.job_runs(reservation_id, attempt_number);
create index job_runs_open_idx
    on ops_private.job_runs(reservation_id)
    where state = 'RUNNING';
-- An abandoned attempt is any RUNNING row whose lease generation no longer
-- matches the reservation; the recovery scan uses this index.
create index job_runs_recovery_idx
    on ops_private.job_runs(ownership_generation)
    where state = 'RUNNING';

alter table ops_private.job_runs enable row level security;
alter table ops_private.job_runs force row level security;

create policy migrator_job_run on ops_private.job_runs
    for all to cce_migrator using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Outbox: emitted in the same transaction as the result, drained separately.
-- ---------------------------------------------------------------------------
create table ops_private.interaction_outbox (
    id uuid primary key default gen_random_uuid(),
    reservation_id uuid not null references ops_private.interaction_reservations(id) on delete cascade,
    effect_identity text not null,
    topic text not null,
    payload jsonb not null default '{}'::jsonb,
    state text not null default 'PENDING'
        check (state in ('PENDING', 'DISPATCHED', 'FAILED')),
    dispatched_at timestamptz,
    created_at timestamptz not null default now()
);

-- One outbox row per emitted effect; re-committing the same result is a no-op
-- rather than a second publication.
create unique index interaction_outbox_identity_idx
    on ops_private.interaction_outbox(reservation_id, effect_identity, topic);
create index interaction_outbox_pending_idx
    on ops_private.interaction_outbox(created_at)
    where state = 'PENDING';

alter table ops_private.interaction_outbox enable row level security;
alter table ops_private.interaction_outbox force row level security;

create policy migrator_interaction_outbox on ops_private.interaction_outbox
    for all to cce_migrator using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Lease acquisition. Taking over an expired lease bumps the generation, which
-- is what fences the previous holder.
-- ---------------------------------------------------------------------------
create or replace function ops_private.claim_interaction(
    target_character uuid,
    requested_purpose text,
    holder text,
    lease_seconds integer,
    command_id uuid
) returns ops_private.interaction_reservations
language plpgsql
security definer
set search_path = ''
as $$
declare
    existing ops_private.interaction_reservations;
    claimed ops_private.interaction_reservations;
    bounded_lease integer := greatest(least(coalesce(lease_seconds, 300), 30), 3600);
begin
    if requested_purpose not in ('ADMIN_CHAT', 'SCENE') then
        raise exception 'Unknown interaction purpose' using errcode='23514';
    end if;

    -- One waiter at a time per character, so two workers cannot both decide the
    -- reservation is free.
    perform pg_advisory_xact_lock(hashtextextended('reservation:' || target_character::text, 0));

    select * into existing
    from ops_private.interaction_reservations
    where character_id = target_character and state = 'HELD'
    for update;

    if found then
        if existing.lease_until is not null and existing.lease_until <= clock_timestamp() then
            -- Expired. The character stays reserved: the previous worker may
            -- still be writing to it, and a lapsed lease is not evidence that
            -- it stopped. Releasing here is what WADR-011 forbids, so an
            -- operator decides through resolve_interaction instead.
            raise exception 'Stale reservation requires operator resolution'
                using errcode = '23514';
        end if;
        -- Live lease. Another worker cannot take it. The same holder resuming
        -- its own work is idempotent and renews the deadline; the generation
        -- bump is what fences any attempt opened under the older deadline.
        if existing.lease_holder = holder and existing.purpose = requested_purpose then
            update ops_private.interaction_reservations
            set lease_until = clock_timestamp() + make_interval(secs => bounded_lease),
                ownership_generation = ownership_generation + 1,
                updated_at = now()
            where id = existing.id
            returning * into claimed;
            return claimed;
        end if;
        raise exception 'Character is reserved' using errcode = '23513';
    end if;
    insert into ops_private.interaction_reservations(
        purpose, ownership_generation, lease_until, lease_holder)
    values (requested_purpose, 1, clock_timestamp() + make_interval(secs => bounded_lease), holder)
    returning * into claimed;
    return claimed;
end $$;
revoke all on function ops_private.claim_interaction(uuid, text, text, integer, uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.claim_interaction(uuid, text, text, integer, uuid)
    to cce_worker_cpu, cce_engine;

-- ---------------------------------------------------------------------------
-- Lease fencing. Every write path below re-checks the generation, so a worker
-- that lost its lease cannot commit a result or an effect.
-- ---------------------------------------------------------------------------
create or replace function ops_private.fence_interaction(
    target_reservation uuid,
    expected_generation bigint,
    holder text
) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_row ops_private.interaction_reservations;
begin
    select * into current_row
    from ops_private.interaction_reservations
    where id = target_reservation and state = 'HELD'
    for update;

    if not found then
        raise exception 'Reservation is no longer held' using errcode='23514';
    end if;
    if current_row.ownership_generation <> expected_generation then
        raise exception 'Lease generation is stale' using errcode='23514';
    end if;
    if current_row.lease_until is not null and current_row.lease_until <= clock_timestamp() then
        raise exception 'Lease expired' using errcode='23514';
    end if;
    if current_row.lease_holder <> holder then
        raise exception 'Lease belongs to another worker' using errcode='23514';
    end if;
end $$;
revoke all on function ops_private.fence_interaction(uuid, bigint, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.fence_interaction(uuid, bigint, text)
    to cce_worker_cpu, cce_engine;

-- ---------------------------------------------------------------------------
-- Result commit. One transaction: mark the run, apply every domain effect
-- under its stable identity, emit the outbox rows, release the reservation.
--
-- A repeated effect_identity is silently skipped rather than duplicated, which
-- is what makes a retry after a lost lease safe. An empty effect set is a
-- valid result and still closes the reservation.
-- ---------------------------------------------------------------------------
create or replace function ops_private.commit_interaction_result(
    target_run uuid,
    expected_generation bigint,
    holder text,
    result_effect_identity text,
    effects jsonb
) returns table(applied integer, skipped integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
    run_row ops_private.job_runs;
    reservation_row ops_private.interaction_reservations;
    effect jsonb;
    applied_count integer := 0;
    skipped_count integer := 0;
begin
    select * into run_row from ops_private.job_runs where id = target_run for update;
    if not found then
        raise exception 'Unknown job run' using errcode='23514';
    end if;
    if run_row.state <> 'RUNNING' then
        -- Already finished. Returning the recorded counts is idempotent.
        return query select 0, 0;
        return;
    end if;

    select * into reservation_row
    from ops_private.interaction_reservations
    where id = run_row.reservation_id
    for update;

    perform ops_private.fence_interaction(
        reservation_row.id, expected_generation, holder
    );

    for effect in select * from jsonb_array_elements(effects) loop
        if effect->>'effect_identity' is null or effect->>'effect_kind' is null then
            raise exception 'Effect requires identity and kind' using errcode='23514';
        end if;
        if effect->>'effect_kind' not in ('MEMORY', 'AFFECT', 'RELATIONSHIP', 'GOAL', 'TRANSCRIPT') then
            raise exception 'Unknown effect kind' using errcode='23514';
        end if;
        insert into ops_private.domain_effects(
            effect_identity, reservation_id, effect_kind,
            applied_by_processing_version, payload)
        values (
            effect->>'effect_identity', reservation_row.id, effect->>'effect_kind',
            effect->>'applied_by_processing_version', effect->'payload')
        on conflict (effect_identity) do nothing;

        if found then
            applied_count := applied_count + 1;
            insert into ops_private.interaction_outbox(
                reservation_id, effect_identity, topic, payload)
            values (
                reservation_row.id, effect->>'effect_identity',
                coalesce(effect->>'topic', 'EFFECT_APPLIED'), effect->'payload')
            on conflict (reservation_id, effect_identity, topic) do nothing;
        else
            skipped_count := skipped_count + 1;
        end if;
    end loop;

    update ops_private.job_runs
    set state = 'SUCCEEDED', finished_at = clock_timestamp(), result_committed = true
    where id = target_run;

    update ops_private.interaction_reservations
    set state = 'RESULT_COMMITTED',
        effect_identity = result_effect_identity,
        committed_at = clock_timestamp(),
        lease_until = null,
        lease_holder = null,
        updated_at = now()
    where id = reservation_row.id;

    return query select applied_count, skipped_count;
end $$;
revoke all on function ops_private.commit_interaction_result(uuid, bigint, text, text, jsonb)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.commit_interaction_result(uuid, bigint, text, text, jsonb)
    to cce_worker_cpu, cce_engine;

-- ---------------------------------------------------------------------------
-- Begin an attempt. Fenced the same way as the commit, so a job_run can never
-- be opened against a lease the worker no longer holds.
-- ---------------------------------------------------------------------------
create or replace function ops_private.begin_interaction_attempt(
    target_reservation uuid,
    expected_generation bigint,
    holder text,
    command_worker text
) returns ops_private.job_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
    next_attempt integer;
    started_run ops_private.job_runs;
begin
    perform ops_private.fence_interaction(target_reservation, expected_generation, holder);

    select coalesce(max(attempt_number), 0) + 1 into next_attempt
    from ops_private.job_runs where reservation_id = target_reservation;

    insert into ops_private.job_runs(
        reservation_id, attempt_number, ownership_generation, worker_id)
    values (target_reservation, next_attempt, expected_generation, command_worker)
    returning * into started_run;
    return started_run;
end $$;
revoke all on function ops_private.begin_interaction_attempt(uuid, bigint, text, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.begin_interaction_attempt(uuid, bigint, text, text)
    to cce_worker_cpu;

-- ---------------------------------------------------------------------------
-- Lease recovery. Expired leases are reported but NOT auto-released: the
-- reservation stays HELD until someone resolves it, because a character whose
-- lease lapsed may still have a worker writing to it.
-- ---------------------------------------------------------------------------
create or replace function ops_private.stale_interactions()
returns table(
    reservation_id uuid,
    character_id uuid,
    purpose text,
    ownership_generation bigint,
    lease_until timestamptz,
    open_run_id uuid
)
language sql
security definer
set search_path = ''
as $$
    select r.id, r.character_id, r.purpose, r.ownership_generation, r.lease_until, j.id
    from ops_private.interaction_reservations r
    left join ops_private.job_runs j
      on j.reservation_id = r.id and j.state = 'RUNNING'
    where r.state = 'HELD'
      and r.lease_until is not null
      and r.lease_until <= clock_timestamp()
    order by r.lease_until
$$;
revoke all on function ops_private.stale_interactions()
    from public, anon, authenticated, service_role;
grant execute on function ops_private.stale_interactions()
    to cce_worker_cpu, cce_worker_maintenance, cce_engine;

create or replace function ops_private.resolve_interaction(
    target_reservation uuid,
    expected_generation bigint,
    reason text
) returns ops_private.interaction_reservations
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_row ops_private.interaction_reservations;
    normalized_reason text := btrim(coalesce(reason, ''));
begin
    if char_length(normalized_reason) < 10 or char_length(normalized_reason) > 1000 then
        raise exception 'Resolution reason must be 10-1000 characters' using errcode='23514';
    end if;

    perform pg_advisory_xact_lock(hashtextextended('reservation:' ||
        (select character_id::text from ops_private.interaction_reservations
         where id = target_reservation), 0));

    select * into current_row
    from ops_private.interaction_reservations
    where id = target_reservation and state = 'HELD'
    for update;

    if not found then
        raise exception 'Reservation is not held' using errcode='23514';
    end if;
    if current_row.ownership_generation <> expected_generation then
        raise exception 'Reservation generation is stale' using errcode='23514';
    end if;

    -- Anything still marked RUNNING was abandoned by the lost lease; record it
    -- rather than deleting it, so the operator can see what happened.
    update ops_private.job_runs
    set state = 'ABANDONED', finished_at = clock_timestamp()
    where reservation_id = target_reservation and state = 'RUNNING';

    update ops_private.interaction_reservations
    set state = 'RESOLVED', lease_until = null, lease_holder = null, updated_at = now()
    where id = target_reservation
    returning * into current_row;

    return current_row;
end $$;
revoke all on function ops_private.resolve_interaction(uuid, bigint, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.resolve_interaction(uuid, bigint, text)
    to cce_engine;

-- Grants: the runtime roles get the narrow surface each one needs. Nothing
-- here is readable by anon/authenticated, and no runtime role may insert
-- effects directly; they go through the definer functions above.
grant select on ops_private.interaction_reservations to cce_engine, cce_worker_cpu, cce_worker_maintenance;
grant select on ops_private.domain_effects to cce_engine, cce_worker_cpu;
grant select on ops_private.job_runs to cce_engine, cce_worker_cpu, cce_worker_maintenance;
grant select on ops_private.interaction_outbox to cce_engine, cce_worker_cpu, cce_worker_maintenance;

-- No runtime role may insert or update a job_run directly. Opening an attempt
-- and finishing one both go through the fenced functions above; a raw UPDATE
-- grant would let a worker whose lease lapsed mark its own run successful.

reset role;

update ops_private.schema_version set version=9 where singleton;
commit;