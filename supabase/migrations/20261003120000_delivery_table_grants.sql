-- M4.6 follow-up: the delivery table has a read policy but no grant.
--
-- Same gap as M4.1 reservations, the M4.2 queue tables and the M4.4
-- processing tables: a row level security policy filters rows for a role that
-- already holds the privilege, it does not confer it. The stream reads the
-- delivery through the Owner plane, which therefore got "permission denied"
-- rather than a row.
--
-- Grants and policies now move together; this is the fourth time.

begin;

set local role cce_migrator;

grant select on ops_private.interaction_deliveries
    to cce_engine, cce_worker_cpu, cce_worker_publisher, cce_worker_maintenance;

reset role;

update ops_private.schema_version set version=16 where singleton;
commit;