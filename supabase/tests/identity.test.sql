begin;
select plan(12);
select has_table('public', 'profiles', 'profiles exist');
select has_table('world_private', 'people', 'people exist');
select has_table('ops_private', 'world_owner', 'owner assignment exists');
select has_table('ops_private', 'identity_audit', 'audit exists');
select ok(not has_table_privilege('authenticated', 'public.profiles', 'INSERT'), 'Data API cannot write profiles');
select ok(not has_table_privilege('anon', 'public.profiles', 'SELECT'), 'anonymous cannot read profiles');
select ok(not has_table_privilege('cce_api', 'ops_private.world_owner', 'INSERT'), 'API cannot elevate role');
select ok(not has_table_privilege('cce_api', 'ops_private.identity_audit', 'UPDATE'), 'API cannot rewrite audit');
select ok(not has_function_privilege('cce_api', 'ops_private.bootstrap_world_owner(uuid,text,text,text)', 'EXECUTE'), 'runtime cannot bootstrap');
select ok(not has_function_privilege('authenticated', 'ops_private.current_identity()', 'EXECUTE'), 'Data API cannot invoke private Auth bridge');
select ok(not has_function_privilege('anon', 'ops_private.bootstrap_world_owner(uuid,text,text,text)', 'EXECUTE'), 'no public definer privilege');
select ok((select bool_and(relrowsecurity and relforcerowsecurity) from pg_class where oid in (
    'public.profiles'::regclass, 'world_private.people'::regclass,
    'ops_private.world_owner'::regclass, 'ops_private.identity_audit'::regclass
)), 'RLS forced on every identity table');
select * from finish();
rollback;
