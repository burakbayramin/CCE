begin;
create extension if not exists pgtap with schema extensions;
select plan(15);

select has_schema('world_private');
select has_schema('ops_private');
select is((select tableowner::text from pg_tables where schemaname = 'ops_private'
    and tablename = 'schema_version'), 'cce_migrator', 'migration role owns app objects');
select ok(not exists(select 1 from pg_roles where rolname like 'cce_%'
    and (rolsuper or rolbypassrls or rolcreaterole or rolcreatedb)), 'no privileged CCE roles');
select ok(not pg_has_role('cce_api', 'cce_migrator', 'MEMBER'), 'API cannot assume owner');
select ok(not pg_has_role('cce_api', 'cce_engine', 'MEMBER'), 'API cannot assume engine');
select ok(not has_schema_privilege('anon', 'world_private', 'USAGE'), 'anonymous world isolation');
select ok(not has_schema_privilege('authenticated', 'ops_private', 'USAGE'), 'user ops isolation');
select ok(not has_schema_privilege('cce_api', 'world_private', 'USAGE'), 'API least privilege');
select ok(not has_schema_privilege('cce_worker_cpu', 'world_private', 'CREATE'), 'worker cannot DDL');
select ok(not has_table_privilege('cce_worker_cpu', 'ops_private.schema_version', 'SELECT'),
    'worker has no blanket ops reads');
select ok((select relrowsecurity and relforcerowsecurity from pg_class
    where oid = 'ops_private.schema_version'::regclass), 'RLS forced on app table');

-- Test-only impersonation, rolled back below; real login tests use cce_api credentials.
grant cce_api to postgres;
grant usage on schema extensions to cce_api;
set local search_path = public, extensions;
set local role cce_api;
select results_eq('select version from ops_private.schema_version', array[4],
    'runtime API can read readiness marker through RLS');
select throws_ok('update ops_private.schema_version set version = 5', '42501',
    'permission denied for table schema_version', 'runtime API cannot alter marker');
reset role;

set local role cce_migrator;
create table public.cce_test_unexposed (id integer);
alter table public.cce_test_unexposed enable row level security;
reset role;
select ok(not has_table_privilege('anon', 'public.cce_test_unexposed', 'SELECT')
    and not has_table_privilege('authenticated', 'public.cce_test_unexposed', 'INSERT'),
    'new tables require explicit grants');
select * from finish();
rollback;
