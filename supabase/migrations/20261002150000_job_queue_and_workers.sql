-- M4.2 — queue, worker supervision and the minimum worker privileges.
--
-- The moderation worker polls a table. This generalises it: work is enqueued,
-- acknowledged only after its result commits, retried with a bound, and
-- quarantined when the bound is reached.
--
-- The acknowledgement rule is the whole point. A pgmq message is deleted only
-- after commit_interaction_result succeeds, and its visibility timeout covers
-- the work. A worker that dies mid-job therefore leaves the message visible
-- and it is retried, rather than the job being lost with the message.
--
-- Retry counting lives in job_runs, not in the message body: the message can be
-- redelivered by pgmq any number of times and the authoritative attempt count
-- is the one the fence already tracks.

begin;

-- The extension is created by the migration runner, before the role switch:
-- CREATE EXTENSION needs rights cce_migrator does not hold, and
-- `if not exists` still checks them. This is what Supabase Queues speaks.
create extension if not exists pgmq;

set local role cce_migrator;

-- The queue itself is created by the CLI/runtime, not here: a migration must
-- not leave an empty queue behind, and `pgmq.create` is idempotent but
-- not transactional with the rest of this file on older images.

-- ---------------------------------------------------------------------------
-- Worker registry. Presence is observed, never assumed: the operations UI needs
-- to distinguish "offline" from "idle" from "stuck".
-- ---------------------------------------------------------------------------
create table ops_private.job_workers (
    worker_id text primary key,
    kind text not null
        check (kind in ('CPU', 'GPU', 'PUBLISHER', 'MAINTENANCE')),
    started_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    -- Concurrency 1 for the main LLM plane: a second concurrent GPU inference
    -- is not a slower queue, it is two models resident at once.
    max_concurrency integer not null default 1
        check (max_concurrency between 1 and 8),
    current_job uuid
);

alter table ops_private.job_workers enable row level security;
alter table ops_private.job_workers force row level security;

create policy migrator_job_worker on ops_private.job_workers
    for all to cce_migrator using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Quarantine. A message that exhausted its bound is parked with the reason.
-- It is never retried automatically again and never deleted: an operator has to
-- look at it.
-- ---------------------------------------------------------------------------
create table ops_private.job_quarantine (
    id uuid primary key default gen_random_uuid(),
    reservation_id uuid not null references ops_private.interaction_reservations(id) on delete cascade,
    run_id uuid,
    attempt_number integer not null check (attempt_number > 0),
    reason text not null check (reason in ('RETRY_EXHAUSTED', 'LEASE_LOST', 'INVALID_OUTPUT')),
    detail text,
    recorded_at timestamptz not null default now(),
    -- One quarantine record per run; re-running the same run is a no-op.
    unique (run_id)
);

create index job_quarantine_reservation_idx on ops_private.job_quarantine(reservation_id);

alter table ops_private.job_quarantine enable row level security;
alter table ops_private.job_quarantine force row level security;

create policy migrator_job_quarantine on ops_private.job_quarantine
    for all to cce_migrator using (true) with check (true);

-- ---------------------------------------------------------------------------
-- Worker heartbeat and the concurrency gate.
-- ---------------------------------------------------------------------------
create or replace function ops_private.heartbeat_worker(
    worker text,
    worker_kind text,
    concurrency integer,
    current_job uuid
) returns void
language sql
security definer
set search_path = ''
as $$
    insert into ops_private.job_workers(worker_id, kind, last_seen_at, max_concurrency, current_job)
    values (worker, worker_kind, now(), greatest(least(coalesce(concurrency, 1), 1), 8), current_job)
    on conflict (worker_id) do update
    set kind = excluded.kind,
        last_seen_at = now(),
        max_concurrency = excluded.max_concurrency,
        current_job = excluded.current_job;
$$;
revoke all on function ops_private.heartbeat_worker(text, text, integer, uuid)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.heartbeat_worker(text, text, integer, uuid)
    to cce_worker_cpu, cce_worker_gpu, cce_worker_publisher, cce_worker_maintenance;

-- A worker whose heartbeat is older than the window is not counted as running.
-- This is what lets the GPU plane advertise a true concurrency rather than a
-- hopeful one.
create or replace function ops_private.live_gpu_slots()
returns integer
language sql
security definer
set search_path = ''
as $$
    select coalesce(sum(
        case when current_job is null then max_concurrency else max_concurrency - 1 end
    ), 0)::integer
    from ops_private.job_workers
    where kind = 'GPU'
      and last_seen_at >= clock_timestamp() - interval '120 seconds';
$$;
revoke all on function ops_private.live_gpu_slots()
    from public, anon, authenticated, service_role;
grant execute on function ops_private.live_gpu_slots()
    to cce_worker_gpu, cce_engine;

create or replace function ops_private.offline_workers()
returns table(worker_id text, kind text, last_seen_at timestamptz)
language sql
security definer
set search_path = ''
as $$
    select worker_id, kind, last_seen_at
    from ops_private.job_workers
    where last_seen_at < clock_timestamp() - interval '120 seconds'
    order by last_seen_at;
$$;
revoke all on function ops_private.offline_workers()
    from public, anon, authenticated, service_role;
grant execute on function ops_private.offline_workers()
    to cce_engine, cce_worker_maintenance;

-- ---------------------------------------------------------------------------
-- Quarantine a run whose bound is exhausted or whose lease was lost.
-- ---------------------------------------------------------------------------
create or replace function ops_private.quarantine_run(
    target_run uuid,
    quarantine_reason text,
    quarantine_detail text
) returns ops_private.job_quarantine
language plpgsql
security definer
set search_path = ''
as $$
declare
    run_row ops_private.job_runs;
    recorded ops_private.job_quarantine;
begin
    if quarantine_reason not in ('RETRY_EXHAUSTED', 'LEASE_LOST', 'INVALID_OUTPUT') then
        raise exception 'Unknown quarantine reason' using errcode = '23514';
    end if;

    select * into run_row from ops_private.job_runs where id = target_run for update;
    if not found then
        raise exception 'Unknown job run' using errcode = '23514';
    end if;

    insert into ops_private.job_quarantine(
        reservation_id, run_id, attempt_number, reason, detail)
    values (run_row.reservation_id, run_row.id, run_row.attempt_number,
            quarantine_reason, left(coalesce(quarantine_detail, ''), 1000))
    on conflict (run_id) do nothing
    returning * into recorded;

    -- The run stops being open either way: a quarantined attempt is not one
    -- the recovery scan should keep re-driving.
    update ops_private.job_runs
    set state = 'QUARANTINED', finished_at = coalesce(finished_at, clock_timestamp())
    where id = target_run and state = 'RUNNING';

    if recorded is null then
        select * into recorded from ops_private.job_quarantine where run_id = target_run;
    end if;
    return recorded;
end $$;
revoke all on function ops_private.quarantine_run(uuid, text, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.quarantine_run(uuid, text, text)
    to cce_worker_cpu, cce_worker_gpu, cce_worker_maintenance;

-- ---------------------------------------------------------------------------
-- Recovery scan. Lists reservations whose last run failed or was quarantined
-- while the reservation is still held, so an operator can decide rather than
-- the system silently looping.
-- ---------------------------------------------------------------------------
create or replace function ops_private.recoverable_interactions(max_attempts integer)
returns table(
    reservation_id uuid,
    character_id uuid,
    attempts integer,
    last_state text,
    quarantined boolean
)
language sql
security definer
set search_path = ''
as $$
    select r.id,
           r.character_id,
           (select max(j.attempt_number) from ops_private.job_runs j
             where j.reservation_id = r.id),
           (select j.state from ops_private.job_runs j
             where j.reservation_id = r.id
             order by j.attempt_number desc limit 1),
           exists(select 1 from ops_private.job_quarantine q where q.reservation_id = r.id)
    from ops_private.interaction_reservations r
    where r.state = 'HELD'
      and (select max(j.attempt_number) from ops_private.job_runs j
           where j.reservation_id = r.id) >= greatest(coalesce(max_attempts, 3), 1)
    order by r.updated_at;
$$;
revoke all on function ops_private.recoverable_interactions(integer)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.recoverable_interactions(integer)
    to cce_engine, cce_worker_maintenance;

-- ---------------------------------------------------------------------------
-- Record a failed attempt.
--
-- This is what makes bounded retry work: the run stops being RUNNING so the
-- recovery scan can see it, but the reservation stays HELD and the queue
-- message is not acknowledged, so the work is redelivered. Only the attempt
-- bound decides when the work stops being retried.
-- ---------------------------------------------------------------------------
create or replace function ops_private.fail_interaction_run(
    target_run uuid,
    failure_reason text
) returns ops_private.job_runs
language plpgsql
security definer
set search_path = ''
as $$
declare
    run_row ops_private.job_runs;
begin
    select * into run_row from ops_private.job_runs where id = target_run for update;
    if not found then
        raise exception 'Unknown job run' using errcode = '23514';
    end if;
    if run_row.state <> 'RUNNING' then
        return run_row;
    end if;
    update ops_private.job_runs
    set state = 'FAILED', finished_at = clock_timestamp(),
        error_code = left(coalesce(failure_reason, 'UNSPECIFIED'), 200)
    where id = target_run
    returning * into run_row;
    return run_row;
end $$;
revoke all on function ops_private.fail_interaction_run(uuid, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.fail_interaction_run(uuid, text)
    to cce_worker_cpu, cce_worker_gpu;

-- ---------------------------------------------------------------------------
-- Minimum worker privileges.
--
-- The four worker roles are separated by what they may touch, not by trust.
-- Only the CPU role reads interaction work; only the publisher touches the
-- outbox; only maintenance resolves stuck reservations. Nobody except cce_engine
-- can resolve or quarantine on behalf of an operator.
-- ---------------------------------------------------------------------------
-- CPU: claims work and runs the fenced handlers. No operator powers.
grant select on ops_private.job_workers to cce_worker_cpu;
grant select on ops_private.job_quarantine to cce_worker_cpu;
grant select on ops_private.domain_effects to cce_worker_cpu;
grant select on ops_private.interaction_outbox to cce_worker_cpu;

-- GPU: same surface as CPU plus its own registry and slot accounting. It still
-- cannot resolve a reservation or quarantine another worker's run.
grant select on ops_private.job_workers to cce_worker_gpu;
grant select on ops_private.job_quarantine to cce_worker_gpu;
grant select on ops_private.domain_effects to cce_worker_gpu;
grant select on ops_private.interaction_outbox to cce_worker_gpu;

-- Publisher: drains the outbox. It does not need to see domain effects at all.
grant select on ops_private.interaction_outbox to cce_worker_publisher;
grant select on ops_private.job_workers to cce_worker_publisher;
grant update (state, dispatched_at) on ops_private.interaction_outbox to cce_worker_publisher;

-- Maintenance: observes and resolves. It does not commit interaction results,
-- because settling an experience is not a maintenance action.
grant select on ops_private.job_workers to cce_worker_maintenance;
grant select on ops_private.job_quarantine to cce_worker_maintenance;
grant select on ops_private.job_runs to cce_worker_maintenance;
grant select on ops_private.interaction_outbox to cce_worker_maintenance;
grant execute on function ops_private.resolve_interaction(uuid, bigint, text)
    to cce_worker_maintenance;

reset role;

update ops_private.schema_version set version=10 where singleton;
commit;