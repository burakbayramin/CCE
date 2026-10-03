-- M4.5 follow-up: the processing tables have read policies but no grants.
--
-- M4.4 created runtime_read_* policies on interaction_turns and the four
-- character state tables, but never granted SELECT. A row level security
-- policy filters rows for a role that already has the privilege; it does not
-- confer it. Every runtime role therefore got "permission denied for table"
-- rather than zero rows, and the difference matters: an empty result is a
-- legitimate answer, a permission error is a bug.
--
-- This is the third time this pattern has appeared (M4.1 reservations, M4.2
-- queue tables, M4.4 processing tables). Grants and policies are asserted
-- together in the pgTAP file rather than written separately.

begin;

set local role cce_migrator;

grant select on ops_private.interaction_turns
    to cce_engine, cce_worker_cpu, cce_worker_gpu,
    cce_worker_publisher, cce_worker_maintenance;

grant select on world_private.character_memories,
    world_private.character_goals,
    world_private.character_affect,
    world_private.character_relationships
    to cce_engine, cce_worker_cpu, cce_worker_gpu;

reset role;

update ops_private.schema_version set version=15 where singleton;
commit;