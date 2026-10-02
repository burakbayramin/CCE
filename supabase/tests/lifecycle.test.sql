begin;
select plan(9);
select ok((select relrowsecurity and relforcerowsecurity from pg_class
    where oid='ops_private.character_lifecycle_events'::regclass),
    'Lifecycle audit uses FORCE RLS');
select ok(not exists(select 1 from unnest(array['anon','authenticated','service_role',
    'cce_api','cce_worker_gpu','cce_worker_cpu','cce_engine']) r
    where has_table_privilege(r,'ops_private.character_lifecycle_events','INSERT,UPDATE,DELETE')),
    'Runtime and Data API cannot write lifecycle audit directly');
select ok(not has_table_privilege('cce_api','ops_private.character_lifecycle_events','SELECT'),
    'Contributor API cannot read lifecycle history');
select ok(not has_table_privilege('cce_engine','world_private.characters','UPDATE'),
    'Lifecycle state is not directly writable by runtime');
select ok(has_function_privilege('cce_engine',
    'ops_private.apply_fixture_character_lifecycle(uuid,text,integer,text,uuid,text)','EXECUTE'),
    'Owner command role can call controlled transition');
select ok(not exists(select 1 from unnest(array['anon','authenticated','service_role',
    'cce_api','cce_worker_gpu','cce_worker_cpu']) r where has_function_privilege(r,
    'ops_private.apply_fixture_character_lifecycle(uuid,text,integer,text,uuid,text)','EXECUTE')),
    'No other runtime role can call lifecycle transition');
select ok(not has_function_privilege('cce_engine',
    'ops_private.current_fixture_character_source(uuid)','EXECUTE'),
    'Source validation helper is private to migration owner');
select ok((select prosecdef and proconfig @> array['search_path=""'] from pg_proc
    where oid='ops_private.apply_fixture_character_lifecycle(uuid,text,integer,text,uuid,text)'::regprocedure),
    'Transition definer has empty search path');
select ok(exists(select 1 from pg_constraint where conrelid='world_private.characters'::regclass
    and conname='character_lifecycle_reasons'), 'State and reason are bound by a database constraint');
select * from finish();
rollback;
