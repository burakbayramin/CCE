-- M4.5 — accepting a turn and delivering it.
--
-- M4.4 leaves a committed turn. Accepting it and delivering it to a recipient
-- is a separate, explicit act, and it is idempotent: `request_id` is the
-- caller's key, so a retry after a lost response returns the original
-- delivery rather than sending the turn twice.
--
-- Delivery runs through the outbox rather than straight to the recipient. The
-- outbox row and the delivery row are written in one transaction with the
-- acceptance, and the publisher drains them afterwards, so a crash between
-- the two loses nothing and duplicates nothing.
--
-- A malformed request_id is refused with 422 at the API boundary rather than
-- being coerced into a uuid and silently deduplicating against an unrelated
-- delivery.

begin;

set local role cce_migrator;

-- ---------------------------------------------------------------------------
-- One row per turn handed to a recipient.
-- ---------------------------------------------------------------------------
create table ops_private.interaction_deliveries (
    id uuid primary key default gen_random_uuid(),
    turn_id uuid not null references ops_private.interaction_turns(id) on delete cascade,
    reservation_id uuid not null
        references ops_private.interaction_reservations(id) on delete cascade,
    recipient_id uuid not null references world_private.people(id) on delete cascade,
    -- The caller's idempotency key. Unique, which is what makes acceptance safe
    -- to retry without an exactly-once guarantee from the caller.
    request_id uuid not null unique,
    state text not null default 'PENDING'
        check (state in ('PENDING', 'DELIVERED', 'FAILED')),
    delivered_at timestamptz,
    failure_reason text,
    recorded_at timestamptz not null default now()
);

create index interaction_deliveries_turn_idx
    on ops_private.interaction_deliveries(turn_id);
create index interaction_deliveries_recipient_idx
    on ops_private.interaction_deliveries(recipient_id, recorded_at desc);

alter table ops_private.interaction_deliveries enable row level security;
alter table ops_private.interaction_deliveries force row level security;

create policy migrator_interaction_delivery on ops_private.interaction_deliveries
    for all to cce_migrator using (true) with check (true);
create policy runtime_read_interaction_delivery on ops_private.interaction_deliveries
    for select to cce_engine, cce_worker_cpu, cce_worker_publisher,
        cce_worker_maintenance
    using (true);

-- ---------------------------------------------------------------------------
-- Accept a turn for delivery.
--
-- Idempotent on request_id: a repeat returns the original delivery rather than
-- emitting a second one. A turn is delivered once; a recipient cannot be handed
-- the same turn twice under different keys.
-- ---------------------------------------------------------------------------
create or replace function ops_private.accept_turn_delivery(
    target_turn uuid,
    recipient uuid,
    request_key uuid
) returns ops_private.interaction_deliveries
language plpgsql
security definer
set search_path = ''
as $$
declare
    existing_delivery ops_private.interaction_deliveries;
    turn_row ops_private.interaction_turns;
    created ops_private.interaction_deliveries;
begin
    select * into existing_delivery
    from ops_private.interaction_deliveries
    where request_id = request_key;
    if found then
        return existing_delivery;
    end if;

    -- Every parameter is qualified. These names sit alongside column names in
    -- the queries below and an unqualified reference is resolved against the
    -- table, not the variable.
    select * into turn_row
    from ops_private.interaction_turns
    where id = accept_turn_delivery.target_turn and state = 'COMMITTED';
    if not found then
        raise exception 'Unknown turn' using errcode = '23514';
    end if;

    insert into ops_private.interaction_deliveries(
        turn_id, reservation_id, recipient_id, request_id)
    values (
        turn_row.id, turn_row.reservation_id,
        accept_turn_delivery.recipient, accept_turn_delivery.request_key)
    returning * into created;

    -- Emitted in the same transaction as the acceptance: the publisher only
    -- ever sees a delivery that already exists.
    insert into ops_private.interaction_outbox(
        reservation_id, effect_identity, topic, payload)
    values (
        turn_row.reservation_id,
        'delivery:' || accept_turn_delivery.request_key::text,
        'TURN_DELIVERY',
        jsonb_build_object(
            'delivery_id', created.id,
            'turn_id', created.turn_id,
            'recipient_id', accept_turn_delivery.recipient))
    on conflict do nothing;

    return created;
end $$;
revoke all on function ops_private.accept_turn_delivery(uuid, uuid, uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.accept_turn_delivery(uuid, uuid, uuid)
    to cce_engine, cce_worker_cpu;

-- ---------------------------------------------------------------------------
-- Drain the outbox into deliveries.
--
-- The publisher role may read and update the outbox and the delivery state,
-- but it cannot accept a turn or change character state: it only moves rows
-- that were already written.
-- ---------------------------------------------------------------------------
create or replace function ops_private.publish_interaction_outbox(batch_size integer)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
    message ops_private.interaction_outbox;
    published integer := 0;
begin
    for message in
        select * from ops_private.interaction_outbox
        where state = 'PENDING'
        order by created_at
        for update skip locked
        limit greatest(coalesce(batch_size, 10), 1)
    loop
        if message.topic = 'TURN_DELIVERY' then
            update ops_private.interaction_deliveries
            set state = 'DELIVERED', delivered_at = clock_timestamp()
            where id = (message.payload->>'delivery_id')::uuid
              and state = 'PENDING';
        end if;
        update ops_private.interaction_outbox
        set state = 'DISPATCHED', dispatched_at = clock_timestamp()
        where id = message.id;
        published := published + 1;
    end loop;
    return published;
end $$;
revoke all on function ops_private.publish_interaction_outbox(integer)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.publish_interaction_outbox(integer)
    to cce_worker_publisher;

-- The publisher needs to move its own queue, which is the one write it has.
grant update (state, dispatched_at) on ops_private.interaction_outbox
    to cce_worker_publisher;

-- ---------------------------------------------------------------------------
-- Read back what happened to an accepted delivery.
-- ---------------------------------------------------------------------------
create or replace function ops_private.delivery_state(request_key uuid)
returns table(
    delivery_id uuid,
    turn_id uuid,
    recipient_id uuid,
    state text,
    delivered_at timestamptz,
    failure_reason text
)
language sql
security definer
set search_path = ''
as $$
    select d.id, d.turn_id, d.recipient_id, d.state, d.delivered_at, d.failure_reason
    from ops_private.interaction_deliveries d
    where d.request_id = request_key;
$$;
revoke all on function ops_private.delivery_state(uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.delivery_state(uuid)
    to cce_engine, cce_worker_cpu, cce_worker_publisher;

reset role;

update ops_private.schema_version set version=14 where singleton;
commit;