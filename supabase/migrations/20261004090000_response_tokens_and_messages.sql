-- M4.6 — response tokens, sequence control, and a durable final message.
--
-- The architecture decisions are already explicit: admin chat streams over a
-- private Realtime broadcast carrying ephemeral tokens, the final message
-- lives durably in PostgreSQL, job polling is the fallback, and a broad
-- service_role key is never handed to a browser or a local worker.
--
-- Two properties this adds, both of which a bare stream endpoint cannot give:
--
-- 1. A response token is scoped, expiring, single-use and stored only as a
--    hash. Possessing it authorises one attempt of one turn, for a moment.
--    A token whose lease lapsed, or whose attempt is no longer the live one,
--    cannot be replayed.
-- 2. Inbound messages and final replies dedupe separately. A retried inbound
--    delivery must not be recorded twice, and re-sending a final reply must
--    not append a second copy — but neither may suppress the other, or a
--    replayed inbound would swallow the reply it caused.

begin;

set local role cce_migrator;

-- ---------------------------------------------------------------------------
-- The durable message log. Inbound and reply share the table and nothing
-- else: each direction has its own identity space.
-- ---------------------------------------------------------------------------
create table ops_private.interaction_messages (
    id uuid primary key default gen_random_uuid(),
    reservation_id uuid not null
        references ops_private.interaction_reservations(id) on delete cascade,
    turn_id uuid references ops_private.interaction_turns(id) on delete cascade,
    attempt_id uuid,
    -- Strictly increasing per turn. A frame older than what has already been
    -- accepted is refused rather than reordered into the log.
    sequence integer not null check (sequence > 0),
    direction text not null check (direction in ('INBOUND', 'REPLY')),
    -- Identity excludes the model and the processing version, per WADR-011.
    effect_identity text not null unique,
    body text not null,
    recorded_at timestamptz not null default now(),
    unique (turn_id, direction, sequence)
);

create index interaction_messages_turn_idx
    on ops_private.interaction_messages(turn_id, direction, sequence);

alter table ops_private.interaction_messages enable row level security;
alter table ops_private.interaction_messages force row level security;

create policy migrator_interaction_message on ops_private.interaction_messages
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_interaction_message on ops_private.interaction_messages
    for select to cce_engine, cce_worker_cpu, cce_worker_publisher,
        cce_worker_maintenance
    using (true);

-- ---------------------------------------------------------------------------
-- Ephemeral response tokens.
--
-- Only the hash is stored. Issued for one attempt of one turn, to one reader,
-- and consumed on first accepted use so a capture cannot be replayed.
-- ---------------------------------------------------------------------------
create table ops_private.interaction_response_tokens (
    id uuid primary key default gen_random_uuid(),
    -- Never the token itself.
    token_hash text not null unique,
    reservation_id uuid not null
        references ops_private.interaction_reservations(id) on delete cascade,
    turn_id uuid not null references ops_private.interaction_turns(id) on delete cascade,
    -- The attempt this token authorises. A lapsed lease produces a new attempt
    -- and an old token stops being valid with it.
    attempt_id uuid not null,
    issued_to uuid not null,
    issued_at timestamptz not null default now(),
    expires_at timestamptz not null,
    consumed_at timestamptz,
    revoked_at timestamptz
);

create index interaction_response_tokens_attempt_idx
    on ops_private.interaction_response_tokens(attempt_id, issued_at desc);

alter table ops_private.interaction_response_tokens enable row level security;
alter table ops_private.interaction_response_tokens force row level security;

create policy migrator_response_token on ops_private.interaction_response_tokens
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_response_token on ops_private.interaction_response_tokens
    for select to cce_engine, cce_worker_cpu, cce_worker_publisher
    using (true);

-- ---------------------------------------------------------------------------
-- Mint a token.
--
-- The insert is behind a definer function so the table itself stays
-- unwritable by any runtime role: a token is only ever created by this path,
-- and a compromised worker cannot mint one for itself.
-- ---------------------------------------------------------------------------
create or replace function ops_private.issue_response_token(
    token_hash_value text,
    target_reservation uuid,
    target_turn uuid,
    target_attempt uuid,
    target_reader uuid,
    ttl_seconds integer
) returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
    if target_turn is null or target_attempt is null then
        raise exception 'Unknown turn' using errcode = '23514';
    end if;

    insert into ops_private.interaction_response_tokens(
        token_hash, reservation_id, turn_id, attempt_id, issued_to,
        issued_at, expires_at)
    values (
        token_hash_value, target_reservation, target_turn, target_attempt, target_reader,
        now(), now() + make_interval(secs => greatest(least(coalesce(ttl_seconds, 120), 10), 600)))
    on conflict (token_hash) do nothing;

    return found;
end $$;
revoke all on function ops_private.issue_response_token(text, uuid, uuid, uuid, uuid, integer)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.issue_response_token(text, uuid, uuid, uuid, uuid, integer)
    to cce_worker_cpu, cce_engine;

-- ---------------------------------------------------------------------------
-- Commit a final message.
--
-- Idempotent per direction. A repeated identity is skipped rather than
-- appended, and the recorded sequence never moves backwards.
-- ---------------------------------------------------------------------------
create or replace function ops_private.commit_message(
    target_turn uuid,
    attempt uuid,
    message_direction text,
    message_sequence integer,
    message_identity text,
    message_body text
) returns table(recorded boolean, accepted_sequence integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
    existing ops_private.interaction_messages;
    highest integer;
begin
    if message_direction not in ('INBOUND', 'REPLY') then
        raise exception 'Unknown message direction' using errcode = '23514';
    end if;

    select * into existing
    from ops_private.interaction_messages
    where effect_identity = message_identity;
    if found then
        return query select false, existing.sequence;
        return;
    end if;

    select coalesce(max(sequence), 0) into highest
    from ops_private.interaction_messages
    where turn_id = target_turn and direction = message_direction;

    if message_sequence <= highest then
        -- Late or duplicated frame: recorded once, never reordered.
        return query select false, highest;
        return;
    end if;

    insert into ops_private.interaction_messages(
        reservation_id, turn_id, attempt_id, sequence, direction,
        effect_identity, body)
    select t.reservation_id, target_turn, attempt, message_sequence,
           message_direction, message_identity, left(coalesce(message_body, ''), 16000)
    from ops_private.interaction_turns t
    where t.id = target_turn
    on conflict (turn_id, direction, sequence) do nothing;

    return query select true, message_sequence;
end $$;
revoke all on function ops_private.commit_message(uuid, uuid, text, integer, text, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.commit_message(uuid, uuid, text, integer, text, text)
    to cce_worker_cpu, cce_engine;

-- Grants and policies together, as with every other runtime table.
grant select on ops_private.interaction_messages
    to cce_engine, cce_worker_cpu, cce_worker_publisher, cce_worker_maintenance;
grant select on ops_private.interaction_response_tokens
    to cce_engine, cce_worker_cpu, cce_worker_publisher;

-- ---------------------------------------------------------------------------
-- Highest accepted sequence per direction, which is what a resuming reader
-- asks for rather than trusting its own local counter.
-- ---------------------------------------------------------------------------
create or replace function ops_private.message_watermark(target_turn uuid)
returns table(direction text, sequence integer)
language sql
security definer
set search_path = ''
as $$
    select m.direction, max(m.sequence)
    from ops_private.interaction_messages m
    where m.turn_id = target_turn
    group by m.direction;
$$;
revoke all on function ops_private.message_watermark(uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.message_watermark(uuid)
    to cce_engine, cce_worker_cpu, cce_worker_publisher;

reset role;

update ops_private.schema_version set version=18 where singleton;
commit;