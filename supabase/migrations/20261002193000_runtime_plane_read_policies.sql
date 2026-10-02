-- M4.1/M4.2 follow-up: the worker plane could not read its own state.
--
-- M4.1 granted SELECT on interaction_reservations, domain_effects, job_runs and
-- interaction_outbox to the runtime roles, and M4.2 granted the same on
-- job_workers and job_quarantine. Every one of those tables carries FORCE row
-- level security with a policy for cce_migrator only, so a worker's SELECT
-- matched zero rows and silently returned nothing.
--
-- The grants were therefore inert: a worker could claim a reservation through
-- the definer functions but could not observe it, its runs, or the queue
-- registry it is supposed to heartbeat into.
--
-- These policies give the runtime plane read-only visibility of operational
-- state. They grant SELECT only. No runtime role may insert or update these
-- tables directly, so the fence in the definer functions remains the only way
-- to change an interaction.

begin;

set local role cce_migrator;

create policy runtime_read_interaction_reservation
    on ops_private.interaction_reservations
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

create policy runtime_read_domain_effect
    on ops_private.domain_effects
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

create policy runtime_read_job_run
    on ops_private.job_runs
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

create policy runtime_read_interaction_outbox
    on ops_private.interaction_outbox
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

create policy runtime_read_job_worker
    on ops_private.job_workers
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

create policy runtime_read_job_quarantine
    on ops_private.job_quarantine
    for select to cce_engine, cce_worker_cpu, cce_worker_gpu,
        cce_worker_publisher, cce_worker_maintenance
    using (true);

reset role;

update ops_private.schema_version set version=12 where singleton;
commit;