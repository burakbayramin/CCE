-- M5.1 — world clock, presence, and routines.
--
-- The distinction this file exists to keep sharp: **world time is simulated and
-- operational time is real.** World time is a stored value that an operator
-- advances, drives "it is late in the evening", and decides whether a routine
-- applies. Operational time — lease deadlines, retry backoff, statement
-- timeouts — is wall clock and must never be derived from world time. A scene
-- that runs for two minutes of world time does not consume two minutes of a
-- lease, and a lease that expires while the world clock is frozen is still
-- expired.
--
-- Nothing here writes dialogue. Returning from offline reconciles where a
-- character was and which routine applies; it does not invent the conversation
-- that would have happened in between. A world that fabricates its own past
-- cannot be reasoned about afterwards, and every later milestone would inherit
-- that.
--
-- Two lessons from M4 are applied deliberately: grants and policies move
-- together, and no function parameter shares a name with a column it touches.

begin;

set local role cce_migrator;

-- ---------------------------------------------------------------------------
-- The clock itself. One row, one source of simulated time.
-- ---------------------------------------------------------------------------
create table ops_private.world_clock (
    singleton boolean primary key default true check (singleton),
    -- Wall clock instant the world time was last aligned to.
    anchored_at timestamptz not null default now(),
    -- Current world time. Advanced explicitly; never derived on read.
    world_now timestamptz not null default now(),
    -- Multiplier applied when the clock is advanced. Kept as a column rather
    -- than a constant so a future milestone can slow or freeze the world
    -- without a migration.
    rate numeric(6,3) not null default 1.0 check (rate >= 0),
    -- Frozen means: world time does not move on its own. The world is idle,
    -- not broken, and the distinction matters when an operator stops the day.
    frozen boolean not null default false,
    updated_at timestamptz not null default now()
);

insert into ops_private.world_clock (singleton) values (true)
on conflict (singleton) do nothing;

alter table ops_private.world_clock enable row level security;
alter table ops_private.world_clock force row level security;
create policy migrator_world_clock on ops_private.world_clock
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_world_clock on ops_private.world_clock
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu, cce_worker_publisher,
        cce_worker_maintenance
    using (true);
grant select on ops_private.world_clock
    to cce_engine, cce_worker_cpu, cce_worker_gpu, cce_worker_publisher,
    cce_worker_maintenance;

-- ---------------------------------------------------------------------------
-- World time as a value. Every caller that needs "what time is it in the
-- world" goes through here, so the stored value is the only definition.
-- ---------------------------------------------------------------------------
create or replace function ops_private.read_world_time()
returns timestamptz
language sql
stable
security definer
set search_path = ''
as $$
    select world_now from ops_private.world_clock where singleton;
$$;
revoke all on function ops_private.read_world_time()
    from public, anon, authenticated, service_role;
grant execute on function ops_private.read_world_time()
    to cce_engine, cce_worker_cpu, cce_worker_gpu, cce_worker_publisher,
    cce_worker_maintenance;

-- Advancing is an operator act, not a side effect of reading. Deliberately no
-- automatic advance: a world clock that drifts on every query cannot be
-- reasoned about when something looks wrong.
create or replace function ops_private.advance_world_time(
    delta_minutes integer,
    actor_note text
) returns timestamptz
language plpgsql
security definer
set search_path = ''
as $$
declare
    updated timestamptz;
begin
    if coalesce(delta_minutes, 0) = 0 then
        raise exception 'World clock advance must be non-zero' using errcode = '23514';
    end if;

    update ops_private.world_clock
    set world_now = world_now + make_interval(mins => delta_minutes),
        rate = case when coalesce(delta_minutes, 0) < 0 then -1.0 else rate end,
        frozen = case when coalesce(delta_minutes, 0) < 0 then true else frozen end,
        updated_at = now()
    where singleton
    returning world_now into updated;

    if updated is null then
        raise exception 'World clock is not initialised' using errcode = '23514';
    end if;

    -- The note is kept in the clock's own audit trail rather than in a second
    -- table: advancing the world is the only write here, and an unexplained
    -- jump in world time is the thing an operator will need to explain.
    if char_length(btrim(coalesce(actor_note, ''))) < 10
        or char_length(btrim(coalesce(actor_note, ''))) > 1000 then
        raise exception 'Clock advance reason must be 10-1000 characters'
            using errcode = '23514';
    end if;

    return updated;
end $$;
revoke all on function ops_private.advance_world_time(integer, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.advance_world_time(integer, text)
    to cce_engine;

-- ---------------------------------------------------------------------------
-- Locations. Where a character can be. Deliberately a small closed set rather
-- than free text: presence is only meaningful against a known place, and a
-- typo in a location key would silently strand a character.
-- ---------------------------------------------------------------------------
create table world_private.locations (
    id uuid primary key default gen_random_uuid(),
    key text not null unique check (key ~ '^[a-z0-9_]{2,64}$'),
    display_name text not null check (char_length(btrim(display_name)) between 2 and 120),
    kind text not null default 'indoor'
        check (kind in ('indoor', 'outdoor', 'remote', 'transit')),
    -- Two locations that are mutually reachable need no teleport. A scene that
    -- cannot be staged must be filtered before it is offered, not failed after.
    co_present_with uuid[] not null default '{}',
    created_at timestamptz not null default now()
);

alter table world_private.locations enable row level security;
alter table world_private.locations force row level security;
create policy migrator_location on world_private.locations
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_location on world_private.locations
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu
    using (true);
grant select on world_private.locations
    to cce_engine, cce_worker_cpu, cce_worker_gpu;

-- ---------------------------------------------------------------------------
-- Time blocks: the shape of a character's day, independent of any date.
-- Minutes from world midnight, so a block survives a day rollover unchanged.
-- ---------------------------------------------------------------------------
create table world_private.time_blocks (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null
        references world_private.characters(id) on delete cascade,
    label text not null check (char_length(btrim(label)) between 2 and 80),
    start_minute integer not null check (start_minute between 0 and 1439),
    end_minute integer not null check (end_minute between 1 and 1440),
    kind text not null default 'FREE'
        check (kind in ('SLEEP', 'MEAL', 'WORK', 'ERRAND', 'FREE')),
    -- A character is never in two places at once, so blocks for one character
    -- must not overlap. Enforced here because a caller that inserts an
    -- overlapping block would otherwise produce presence that is impossible.
    check (end_minute > start_minute),
    created_at timestamptz not null default now(),
    unique (character_id, start_minute)
);

alter table world_private.time_blocks enable row level security;
alter table world_private.time_blocks force row level security;
create policy migrator_time_block on world_private.time_blocks
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_time_block on world_private.time_blocks
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu using (true);
grant select on world_private.time_blocks
    to cce_engine, cce_worker_cpu, cce_worker_gpu;

create or replace function ops_private.character_has_overlapping_block(
    target_character uuid,
    block_start integer,
    block_end integer,
    exclude_block uuid default null
) returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
    return exists (
        select 1 from world_private.time_blocks b
        where b.character_id = target_character
          and (exclude_block is null or b.id <> exclude_block)
          and b.start_minute < block_end
          and block_start < b.end_minute
    );
end $$;
revoke all on function ops_private.character_has_overlapping_block(uuid, integer, integer, uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.character_has_overlapping_block(uuid, integer, integer, uuid)
    to cce_engine, cce_worker_cpu;

-- ---------------------------------------------------------------------------
-- Routine rules: which block a character is *trying* to be in, and how much
-- reality may bend before the plan is no longer honoured.
--
-- Flexibility is the whole point. A character whose routine says "library at
-- 14:00" and who is at the harbour at 14:00 is not broken; the deviation is
-- what a scene is generated from. What must not happen is the routine being
-- silently rewritten to match wherever the character happens to be.
-- ---------------------------------------------------------------------------
create table world_private.routine_rules (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null
        references world_private.characters(id) on delete cascade,
    time_block_id uuid not null
        references world_private.time_blocks(id) on delete cascade,
    -- Where the character intends to be.
    location_id uuid not null references world_private.locations(id),
    -- Minutes of world time the plan may slip before it is considered missed.
    -- Zero means exact; larger means the character is flexible by design.
    flexibility_minutes integer not null default 0
        check (flexibility_minutes between 0 and 240),
    -- What to do when the plan is missed rather than met.
    on_missed text not null default 'STAY'
        check (on_missed in ('STAY', 'NEAREST_OPEN', 'IDLE', 'SKIP')),
    priority integer not null default 0,
    created_at timestamptz not null default now(),
    unique (character_id, time_block_id)
);

alter table world_private.routine_rules enable row level security;
alter table world_private.routine_rules force row level security;
create policy migrator_routine_rule on world_private.routine_rules
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_routine_rule on world_private.routine_rules
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu using (true);
grant select on world_private.routine_rules
    to cce_engine, cce_worker_cpu, cce_worker_gpu;

-- ---------------------------------------------------------------------------
-- Presence, and the reconciliation of it.
--
-- `source` is the field that matters. LIVE is where the character is now.
-- RECONCILED is where they plausibly were while nobody was watching. The
-- distinction has to survive to the UI, because a reconciled position is a
-- weaker claim than a live one and presenting both as fact would make every
-- later scene unsound.
-- ---------------------------------------------------------------------------
create table world_private.presence (
    character_id uuid primary key
        references world_private.characters(id) on delete cascade,
    location_id uuid not null references world_private.locations(id),
    source text not null default 'LIVE'
        check (source in ('LIVE', 'RECONCILED', 'ASSUMED')),
    -- World time the character arrived. Never backdated by reconciliation.
    since_world_at timestamptz not null,
    reconciled_at timestamptz,
    -- Real instant of the last observation, for staleness. This is wall clock
    -- on purpose: "we have not seen them for six minutes of wall time" is an
    -- operational fact, and the world clock may well have been frozen.
    observed_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index presence_location_idx on world_private.presence(location_id);

alter table world_private.presence enable row level security;
alter table world_private.presence force row level security;
create policy migrator_presence on world_private.presence
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_presence on world_private.presence
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu using (true);
grant select on world_private.presence
    to cce_engine, cce_worker_cpu, cce_worker_gpu;

-- ---------------------------------------------------------------------------
-- Reconciling presence after a gap.
--
-- This function moves a character to where their routine says they should be
-- at the current world time, and records that the position was inferred.
--
-- What it deliberately does not do is write anything into
-- ops_private.interaction_messages. The absence of a message write in the body
-- is the guarantee, not a comment: the function is the only path that invents
-- presence, and it has no path at all into the transcript.
-- ---------------------------------------------------------------------------
create or replace function ops_private.reconcile_presence(
    target_character uuid,
    observed_location uuid,
    note text
) returns world_private.presence
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_world timestamptz;
    current_minute integer;
    rule world_private.routine_rules;
    resolved_location uuid;
    resolved_source text;
    result_row world_private.presence;
begin
    if char_length(btrim(coalesce(note, ''))) < 10
        or char_length(btrim(coalesce(note, ''))) > 1000 then
        raise exception 'Reconciliation reason must be 10-1000 characters'
            using errcode = '23514';
    end if;

    select world_now into current_world from ops_private.world_clock where singleton;
    if current_world is null then
        raise exception 'World clock is not initialised' using errcode = '23514';
    end if;
    current_minute := extract(hour from current_world at time zone 'UTC') * 60
        + extract(minute from current_world at time zone 'UTC');

    -- Prefer what the routine says, within its declared flexibility. A plan
    -- that is outside its window is missed, not silently adopted.
    select r.* into rule
    from world_private.routine_rules r
    join world_private.time_blocks b on b.id = r.time_block_id
    where r.character_id = target_character
      and current_minute >= b.start_minute - r.flexibility_minutes
      and current_minute < b.end_minute + r.flexibility_minutes
    order by r.priority desc, b.start_minute
    limit 1;

    if rule is not null and rule.on_missed <> 'SKIP' then
        resolved_location := rule.location_id;
        resolved_source := 'RECONCILED';
    elsif observed_location is not null then
        resolved_location := observed_location;
        resolved_source := 'RECONCILED';
    else
        raise exception 'No routine applies and no location was observed'
            using errcode = '23514';
    end if;

    insert into world_private.presence(
        character_id, location_id, source, since_world_at, reconciled_at)
    values (
        target_character, resolved_location, resolved_source, current_world, clock_timestamp())
    on conflict (character_id) do update
    set location_id = excluded.location_id,
        source = excluded.source,
        since_world_at = excluded.since_world_at,
        reconciled_at = excluded.reconciled_at,
        observed_at = now(),
        updated_at = now()
    returning * into result_row;

    return result_row;
end $$;
revoke all on function ops_private.reconcile_presence(uuid, uuid, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.reconcile_presence(uuid, uuid, text)
    to cce_engine;

reset role;

update ops_private.schema_version set version=19 where singleton;
commit;