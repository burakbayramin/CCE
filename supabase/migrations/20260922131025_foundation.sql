begin;

-- Roles survive a local DB reset. Passwords are provisioned outside migrations.
do $$
declare
    role_name text;
begin
    foreach role_name in array array[
        'cce_migrator', 'cce_api', 'cce_engine', 'cce_worker_gpu',
        'cce_worker_cpu', 'cce_worker_publisher', 'cce_worker_maintenance'
    ] loop
        if not exists (select 1 from pg_roles where rolname = role_name) then
            execute format('create role %I nologin', role_name);
        end if;
        if exists (select 1 from pg_roles where rolname = role_name
            and (rolsuper or rolcreatedb or rolcreaterole or rolreplication or rolbypassrls)) then
            raise exception 'CCE role has unexpected privileges: %', role_name;
        end if;
    end loop;
end
$$;

grant cce_migrator to postgres;
create schema world_private authorization cce_migrator;
create schema ops_private authorization cce_migrator;
grant usage, create on schema public to cce_migrator;

revoke all on schema public from public, anon, authenticated;
grant usage on schema public to anon, authenticated, cce_api, cce_engine,
    cce_worker_publisher;
revoke all on schema world_private, ops_private from public, anon, authenticated,
    service_role;
grant usage on schema world_private to cce_engine, cce_worker_gpu, cce_worker_cpu,
    cce_worker_publisher, cce_worker_maintenance;
grant usage on schema ops_private to cce_api, cce_engine, cce_worker_gpu,
    cce_worker_cpu, cce_worker_publisher, cce_worker_maintenance;

-- Supabase defaults must not silently expose future application objects.
alter default privileges for role postgres in schema public
    revoke all on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
    revoke all on sequences from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
    revoke all on functions from public, anon, authenticated, service_role;
alter default privileges for role cce_migrator
    revoke execute on functions from public;
alter default privileges for role cce_migrator in schema public, world_private, ops_private
    revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role cce_migrator in schema public, world_private, ops_private
    revoke all on sequences from public, anon, authenticated, service_role;

set local role cce_migrator;
create table ops_private.schema_version (
    singleton boolean primary key default true check (singleton),
    version integer not null check (version > 0)
);
insert into ops_private.schema_version (version) values (1);
alter table ops_private.schema_version enable row level security;
alter table ops_private.schema_version force row level security;
grant select on ops_private.schema_version to cce_api;
create policy api_read_schema_version on ops_private.schema_version
    for select to cce_api using (true);
reset role;

commit;
