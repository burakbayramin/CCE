begin;
select plan(12);
select ok(bool_and(relrowsecurity and relforcerowsecurity), 'All activation tables use FORCE RLS')
from pg_class where oid in ('ops_private.fixture_activation_policy'::regclass,
    'ops_private.character_capacity'::regclass,'world_private.characters'::regclass,
    'world_private.character_initial_state'::regclass,
    'ops_private.character_activation_events'::regclass,
    'ops_private.character_capacity_events'::regclass);
select ok(not exists(select 1 from unnest(array['anon','authenticated','service_role',
    'cce_api','cce_worker_gpu','cce_engine']) r cross join unnest(array[
    'ops_private.fixture_activation_policy','ops_private.character_capacity',
    'world_private.characters','world_private.character_initial_state',
    'ops_private.character_activation_events','ops_private.character_capacity_events']) t
    where has_table_privilege(r,t,'INSERT,UPDATE,DELETE')), 'No runtime or Data API raw DML');
select ok(not has_table_privilege('cce_engine','ops_private.fixture_activation_policy','SELECT'),
    'Runtime cannot inspect or toggle the fixture activation gate');
select ok(not has_table_privilege('cce_api','world_private.characters','SELECT'),
    'Contributor API cannot read runtime characters');
select ok(has_function_privilege('cce_engine',
    'ops_private.activate_fixture_character(uuid,integer,uuid,uuid,text,text)','EXECUTE'),
    'Owner command role can invoke fixture activation');
select ok(has_function_privilege('cce_engine',
    'ops_private.set_character_capacity(integer,integer,text,uuid)','EXECUTE'),
    'Owner command role can invoke capacity change');
select ok(not exists(select 1 from unnest(array['anon','authenticated','service_role',
    'cce_api','cce_worker_gpu']) r where has_function_privilege(r,
    'ops_private.activate_fixture_character(uuid,integer,uuid,uuid,text,text)','EXECUTE')
    or has_function_privilege(r,
    'ops_private.set_character_capacity(integer,integer,text,uuid)','EXECUTE')),
    'No other runtime role can invoke privileged commands');
select ok(bool_and(prosecdef and proconfig @> array['search_path=""']),
    'Privileged commands are definers with empty search paths')
from pg_proc where oid in (
    'ops_private.activate_fixture_character(uuid,integer,uuid,uuid,text,text)'::regprocedure,
    'ops_private.set_character_capacity(integer,integer,text,uuid)'::regprocedure);
select throws_ok('update ops_private.character_capacity set active_limit=51', '23514',
    null, 'Database enforces the maximum of 50');
select throws_ok('update ops_private.character_capacity set active_limit=-1', '23514',
    null, 'Negative capacity is rejected');
select ok(exists(select 1 from pg_constraint where conrelid='world_private.characters'::regclass
    and contype='c' and pg_get_constraintdef(oid)='CHECK (is_fixture)'),
    'Character storage explicitly permits fixtures only in this milestone');
select ok(not exists(select 1 from pg_auth_members m join pg_roles parent on parent.oid=m.roleid
    join pg_roles child on child.oid=m.member where parent.rolname='cce_migrator'
    and child.rolname in ('cce_api','cce_engine','cce_worker_gpu','anon','authenticated','service_role')),
    'No runtime role inherits migration ownership');
select * from finish();
rollback;
