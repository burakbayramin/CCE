-- M4.1 follow-up: claim_interaction never stored the character it reserved.
--
-- The INSERT listed purpose, ownership_generation, lease_until and lease_holder
-- but not character_id, which is NOT NULL with no default. Every claim on a
-- fresh character therefore raised a not-null violation.
--
-- The error was very hard to read because the application mapped it by
-- scanning the database message for a word: the echoed statement contains the
-- bind parameter ":lease", so a lease refusal was reported for a constraint
-- failure. Mapping is exact now, but the migration error is fixed here rather
-- than papered over.
--
-- The same migration corrects the lease clamp, which always evaluated to
-- 3600: greatest(least(x, 30), 3600) is 3600 for every input. A caller asking
-- for a thirty second lease got an hour, which defeats lease-based recovery.

begin;

set local role cce_migrator;

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
    bounded_lease integer := least(
        greatest(coalesce(lease_seconds, 300), 30), 3600
    );
begin
    if requested_purpose not in ('ADMIN_CHAT', 'SCENE') then
        raise exception 'Unknown interaction purpose' using errcode='23514';
    end if;

    -- One waiter at a time per character, so two workers cannot both decide the
    -- reservation is free.
    perform pg_advisory_xact_lock(
        hashtextextended('reservation:' || target_character::text, 0)
    );

    select * into existing
    from ops_private.interaction_reservations
    where character_id = target_character and state = 'HELD'
    for update;

    if found then
        if existing.lease_until is not null
            and existing.lease_until <= clock_timestamp() then
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
        character_id, purpose, ownership_generation, lease_until, lease_holder)
    values (
        target_character, requested_purpose, 1,
        clock_timestamp() + make_interval(secs => bounded_lease), holder
    )
    returning * into claimed;
    return claimed;
end $$;
revoke all on function ops_private.claim_interaction(uuid, text, text, integer, uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.claim_interaction(uuid, text, text, integer, uuid)
    to cce_worker_cpu, cce_engine;

reset role;

update ops_private.schema_version set version=11 where singleton;
commit;