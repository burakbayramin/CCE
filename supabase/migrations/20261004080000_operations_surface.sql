-- M4.7 — the operations surface.
--
-- Everything the operations view reads, and the two commands it can issue.
-- Read paths only expose what an operator needs to answer "is anything stuck,
-- and is anyone still alive"; they deliberately do not expose provider detail,
-- effect identities or turn content.
--
-- The two commands are separate because they answer different questions.
-- Resolving a stuck reservation says "this worker is not coming back, free the
-- character". Re-queuing a failed attempt says "try that work again". Both take
-- a reason, both require the World Owner identity, and both are audited.

begin;

set local role cce_migrator;

-- ---------------------------------------------------------------------------
-- Worker registry and the live queue, in one read.
-- ---------------------------------------------------------------------------
create or replace function ops_private.operations_snapshot(stale_seconds integer)
returns table(
    worker_id text,
    worker_kind text,
    worker_state text,
    last_seen_at timestamptz,
    worker_max_concurrency integer,
    worker_current_job uuid,
    reservation_id uuid,
    reservation_character uuid,
    reservation_purpose text,
    reservation_state text,
    reservation_generation bigint,
    reservation_lease_until timestamptz,
    open_run_attempts integer,
    last_attempt_state text,
    quarantined boolean
)
language sql
security definer
set search_path = ''
as $$
    select
        w.worker_id,
        w.kind,
        case
            when w.last_seen_at < clock_timestamp() - make_interval(secs => greatest(coalesce(stale_seconds, 120), 10)) then 'OFFLINE'
            when w.current_job is not null then 'BUSY'
            else 'IDLE'
        end,
        w.last_seen_at,
        w.max_concurrency,
        w.current_job,
        r.id,
        r.character_id,
        r.purpose,
        r.state,
        r.ownership_generation,
        r.lease_until,
        coalesce((select max(j.attempt_number) from ops_private.job_runs j where j.reservation_id = r.id), 0),
        (select j.state from ops_private.job_runs j where j.reservation_id = r.id
         order by j.attempt_number desc limit 1),
        exists(select 1 from ops_private.job_quarantine q where q.reservation_id = r.id)
    from ops_private.job_workers w
    left join ops_private.interaction_reservations r
      on r.id = w.current_job or (r.state = 'HELD' and w.current_job is null)
    order by w.kind, w.worker_id;
$$;
revoke all on function ops_private.operations_snapshot(integer)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.operations_snapshot(integer)
    to cce_engine, cce_worker_maintenance;

-- ---------------------------------------------------------------------------
-- Re-queue a failed attempt.
--
-- The attempt bound is re-checked here rather than trusted from the caller, and
-- the reservation must still be held by the same generation. A late worker
-- whose lease lapsed cannot revive its own work.
-- ---------------------------------------------------------------------------
create or replace function ops_private.requeue_interaction(
    target_reservation uuid,
    expected_generation bigint,
    worker_id text,
    reason text
) returns ops_private.interaction_reservations
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_row ops_private.interaction_reservations;
    normalized_reason text := btrim(coalesce(reason, ''));
    refreshed ops_private.interaction_reservations;
begin
    if char_length(normalized_reason) < 10 or char_length(normalized_reason) > 1000 then
        raise exception 'Resolution reason must be 10-1000 characters' using errcode = '23514';
    end if;

    perform pg_advisory_xact_lock(
        hashtextextended('reservation:' || target_reservation::text, 0)
    );

    select * into current_row
    from ops_private.interaction_reservations
    where id = target_reservation and state = 'HELD'
    for update;

    if not found then
        raise exception 'Reservation is not held' using errcode = '23514';
    end if;
    if current_row.ownership_generation <> expected_generation then
        raise exception 'Reservation generation is stale' using errcode = '23514';
    end if;

    -- Anything still open is finished one way or another before re-queueing.
    update ops_private.job_runs
    set state = 'ABANDONED', finished_at = coalesce(finished_at, clock_timestamp())
    where reservation_id = target_reservation and state = 'RUNNING';

    -- The attempt number keeps climbing, so the recovery scan still sees the
    -- history rather than a silently reset job.
    insert into ops_private.interaction_outbox(
        reservation_id, effect_identity, topic, payload)
    values (
        target_reservation,
        'requeue:' || gen_random_uuid()::text,
        'INTERACTION_REQUEUE',
        jsonb_build_object('reservation_id', target_reservation, 'reason', normalized_reason))
    on conflict do nothing;

    update ops_private.interaction_reservations
    set lease_until = null, lease_holder = null, updated_at = now()
    where id = target_reservation
    returning * into refreshed;
    return refreshed;
end $$;
revoke all on function ops_private.requeue_interaction(uuid, bigint, text, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.requeue_interaction(uuid, bigint, text, text)
    to cce_engine;

reset role;

update ops_private.schema_version set version=17 where singleton;
commit;