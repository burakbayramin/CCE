-- M4.4 — the processing pipeline: turns and the state a turn changes.
--
-- M4.1 recorded that effects *happened*. M4.4 records what the character
-- actually became, and binds every write to a source identity so a retry under
-- a different model collides with what already applied instead of duplicating
-- the world's memories.
--
-- Two failure classes, deliberately not treated the same:
--
--   * An effect (memory, affect, goal) failing is fatal. The character's own
--     state would be half-written, so the turn is quarantined and the
--     reservation stays held for an operator.
--   * A relationship failing is recorded and the turn is flagged. Losing a
--     social bond is recoverable; losing the fact that the turn happened, or
--     the character's own state, is not.
--
-- The source identity never contains a model name or a processing version. It
-- is derived from the turn identity and the effect's own content, so the same
-- experience under a different model produces the same key.

begin;

set local role cce_migrator;

-- ---------------------------------------------------------------------------
-- The turn ledger. One row per interaction turn; the transcript lives here
-- rather than in the reservation so history survives the reservation closing.
-- ---------------------------------------------------------------------------
create table ops_private.interaction_turns (
    id uuid primary key default gen_random_uuid(),
    reservation_id uuid not null
        references ops_private.interaction_reservations(id) on delete cascade,
    character_id uuid not null references world_private.characters(id) on delete cascade,
    turn_index integer not null check (turn_index > 0),
    -- Stable and model-independent. This is the identity a retry collapses onto.
    effect_identity text not null,
    prompt_text text,
    response_text text,
    state text not null default 'COMMITTED'
        check (state in ('COMMITTED', 'QUARANTINED')),
    -- Set when a relationship failed but the turn itself was kept.
    flagged boolean not null default false,
    flag_reason text,
    recorded_at timestamptz not null default now(),
    unique (reservation_id, turn_index)
);

create index interaction_turns_character_idx
    on ops_private.interaction_turns(character_id, turn_index);

alter table ops_private.interaction_turns enable row level security;
alter table ops_private.interaction_turns force row level security;

create policy migrator_interaction_turn on ops_private.interaction_turns
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_interaction_turn
    on ops_private.interaction_turns
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

-- ---------------------------------------------------------------------------
-- Character state a turn changes. Every row carries the source identity that
-- produced it, so re-running a turn is a no-op rather than a duplicate.
-- ---------------------------------------------------------------------------
create table world_private.character_memories (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null references world_private.characters(id) on delete cascade,
    source_identity text not null,
    text text not null,
    recorded_at timestamptz not null default now(),
    unique (character_id, source_identity)
);

create table world_private.character_goals (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null references world_private.characters(id) on delete cascade,
    source_identity text not null,
    description text not null,
    state text not null default 'ACTIVE' check (state in ('ACTIVE', 'MET', 'DROPPED')),
    recorded_at timestamptz not null default now(),
    unique (character_id, source_identity)
);

create table world_private.character_affect (
    character_id uuid primary key references world_private.characters(id) on delete cascade,
    source_identity text not null,
    valence numeric(5,4) not null check (valence between -1 and 1),
    arousal numeric(5,4) not null check (arousal between -1 and 1),
    dominance numeric(5,4) not null check (dominance between -1 and 1),
    updated_at timestamptz not null default now()
);

create table world_private.character_relationships (
    character_id uuid not null references world_private.characters(id) on delete cascade,
    subject_id uuid not null references world_private.characters(id) on delete cascade,
    source_identity text not null,
    affinity numeric(5,4) check (affinity between -1 and 1),
    trust numeric(5,4) check (trust between -1 and 1),
    updated_at timestamptz not null default now(),
    primary key (character_id, subject_id, source_identity)
);

alter table world_private.character_memories enable row level security;
alter table world_private.character_memories force row level security;
alter table world_private.character_goals enable row level security;
alter table world_private.character_goals force row level security;
alter table world_private.character_affect enable row level security;
alter table world_private.character_affect force row level security;
alter table world_private.character_relationships enable row level security;
alter table world_private.character_relationships force row level security;

create policy migrator_character_memory on world_private.character_memories
    for all to cce_migrator using (true) with check (true);
create policy migrator_character_goal on world_private.character_goals
    for all to cce_migrator using (true) with check (true);
create policy migrator_character_affect on world_private.character_affect
    for all to cce_migrator using (true) with check (true);
create policy migrator_character_relationship on world_private.character_relationships
    for all to cce_migrator using (true) with check (true);

-- Runtime roles observe a character's own resulting state. They cannot write:
-- only the fenced function below changes character state.
create policy runtime_read_character_memory on world_private.character_memories
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu
    using (true);
create policy runtime_read_character_goal on world_private.character_goals
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu using (true);
create policy runtime_read_character_affect on world_private.character_affect
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu using (true);
create policy runtime_read_character_relationship on world_private.character_relationships
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu using (true);

-- ---------------------------------------------------------------------------
-- Apply a turn.
--
-- One transaction: the turn row, every effect, and the reservation close. An
-- effect failure aborts all of it, so a character is never left half-written.
-- A relationship failure is caught, recorded, and leaves the turn flagged.
-- ---------------------------------------------------------------------------
create or replace function ops_private.apply_interaction_turn(
    target_reservation uuid,
    expected_generation bigint,
    holder text,
    requested_index integer,
    turn_effect_identity text,
    prompt_text text,
    response_text text,
    effects jsonb,
    relationship_effects jsonb
) returns table(turn_id uuid, applied integer, skipped integer, flagged boolean)
language plpgsql
security definer
set search_path = ''
as $$
declare
    run_row ops_private.job_runs;
    reservation_row ops_private.interaction_reservations;
    character uuid;
    effect jsonb;
    relationship jsonb;
    recorded_turn ops_private.interaction_turns;
    applied_count integer := 0;
    skipped_count integer := 0;
    relationship_failure text;
begin
    select * into run_row
    from ops_private.job_runs
    where reservation_id = target_reservation and state = 'RUNNING'
    order by attempt_number desc limit 1;
    if not found then
        raise exception 'Unknown job run' using errcode = '23514';
    end if;

    select * into reservation_row
    from ops_private.interaction_reservations
    where id = target_reservation
    for update;

    perform ops_private.fence_interaction(target_reservation, expected_generation, holder);
    character := reservation_row.character_id;

    insert into ops_private.interaction_turns(
        reservation_id, character_id, turn_index, effect_identity,
        prompt_text, response_text)
    values (
        reservation_row.id, character, requested_index, turn_effect_identity,
        left(coalesce(prompt_text, ''), 8000), left(coalesce(response_text, ''), 8000))
    on conflict (reservation_id, turn_index) do nothing
    returning * into recorded_turn;

    if recorded_turn is null then
        select * into recorded_turn from ops_private.interaction_turns
        where reservation_id = target_reservation
          and turn_index = requested_index;
        -- A repeated turn is a no-op, not a second application.
        return query select recorded_turn.id, 0, 0, recorded_turn.flagged;
        return;
    end if;

    for effect in select * from jsonb_array_elements(coalesce(effects, '[]'::jsonb)) loop
        if effect->>'effect_kind' not in ('MEMORY', 'AFFECT', 'GOAL', 'TRANSCRIPT') then
            raise exception 'Unknown effect kind' using errcode = '23514';
        end if;
        if effect->>'source_identity' is null or effect->>'source_identity' = '' then
            raise exception 'Effect requires identity and kind' using errcode = '23514';
        end if;

        if effect->>'effect_kind' = 'MEMORY' then
            insert into world_private.character_memories(character_id, source_identity, text)
            values (character, effect->>'source_identity', coalesce(effect->>'text', ''))
            on conflict (character_id, source_identity) do nothing;
        elsif effect->>'effect_kind' = 'GOAL' then
            insert into world_private.character_goals(character_id, source_identity, description)
            values (character, effect->>'source_identity', coalesce(effect->>'description', ''))
            on conflict (character_id, source_identity) do nothing;
        elsif effect->>'effect_kind' = 'AFFECT' then
            insert into world_private.character_affect(
                character_id, source_identity, valence, arousal, dominance)
            values (
                character, effect->>'source_identity',
                coalesce((effect->>'valence')::numeric, 0),
                coalesce((effect->>'arousal')::numeric, 0),
                coalesce((effect->>'dominance')::numeric, 0))
            on conflict (character_id) do update
            set valence = excluded.valence, arousal = excluded.arousal,
                dominance = excluded.dominance,
                source_identity = excluded.source_identity, updated_at = now();
        end if;

        if found then applied_count := applied_count + 1;
        else skipped_count := skipped_count + 1;
        end if;
    end loop;

    -- Relationships are isolated: a failure is recorded on the turn rather than
    -- discarding a turn whose effects all applied.
    begin
        for relationship in select * from
            jsonb_array_elements(coalesce(relationship_effects, '[]'::jsonb)) loop
            insert into world_private.character_relationships(
                character_id, subject_id, source_identity, affinity, trust)
            values (
                character,
                (relationship->>'subject_id')::uuid,
                relationship->>'source_identity',
                (relationship->>'affinity')::numeric,
                (relationship->>'trust')::numeric)
            on conflict (character_id, subject_id, source_identity) do update
            set affinity = excluded.affinity, trust = excluded.trust,
                updated_at = now();
        end loop;
    exception when others then
        relationship_failure := 'RELATIONSHIP_UPDATE_FAILED';
    end;

    if relationship_failure is not null then
        update ops_private.interaction_turns
        set flagged = true, flag_reason = relationship_failure
        where id = recorded_turn.id;
    end if;

    update ops_private.job_runs
    set state = 'SUCCEEDED', finished_at = clock_timestamp(), result_committed = true
    where id = run_row.id;

    update ops_private.interaction_reservations
    set state = 'RESULT_COMMITTED',
        effect_identity = turn_effect_identity,
        committed_at = clock_timestamp(),
        lease_until = null, lease_holder = null, updated_at = now()
    where id = reservation_row.id;

    return query select
        recorded_turn.id, applied_count, skipped_count,
        (relationship_failure is not null);
end $$;
revoke all on function ops_private.apply_interaction_turn(
    uuid, bigint, text, integer, text, text, text, jsonb, jsonb)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.apply_interaction_turn(
    uuid, bigint, text, integer, text, text, text, jsonb, jsonb)
    to cce_worker_cpu, cce_engine;

reset role;

update ops_private.schema_version set version=13 where singleton;
commit;
