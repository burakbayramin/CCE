begin;
select plan(14);

select ok(has_function_privilege('cce_worker_cpu',
    'ops_private.moderation_avatar_path(uuid,uuid,uuid)','EXECUTE'),
    'Only DB worker can resolve a live attempt avatar path');
select ok(not has_function_privilege('authenticated',
    'ops_private.moderation_avatar_path(uuid,uuid,uuid)','EXECUTE'),
    'Authenticated clients cannot resolve moderation paths');
select ok(not has_function_privilege('cce_api',
    'ops_private.moderation_avatar_path(uuid,uuid,uuid)','EXECUTE'),
    'API role cannot resolve moderation paths');
select ok(has_function_privilege('cce_worker_cpu',
    'ops_private.claim_moderation_for_worker(uuid)','EXECUTE'),
    'DB worker can atomically bind a claim to its Auth identity');
select ok(not has_function_privilege('authenticated',
    'ops_private.claim_moderation_for_worker(uuid)','EXECUTE'),
    'Auth clients cannot claim moderation jobs');
select ok((select relforcerowsecurity from pg_class
    where oid='ops_private.moderation_jobs'::regclass),
    'Assigned jobs retain FORCE RLS');
select ok(has_function_privilege('authenticated',
    'ops_private.moderation_avatar_storage_access(text)','EXECUTE'),
    'Storage can evaluate the worker read gate');
select ok(not has_function_privilege('anon',
    'ops_private.moderation_avatar_storage_access(text)','EXECUTE'),
    'Anonymous clients cannot evaluate the worker read gate');
select ok(not has_table_privilege('authenticated','ops_private.moderation_jobs','SELECT'),
    'Auth worker cannot read moderation jobs through the Data API');
select is((select count(*)::integer from pg_policies
    where schemaname='storage' and tablename='objects'
        and policyname='cce_moderation_avatar_read' and cmd='SELECT'), 1,
    'Worker has exactly one Storage read policy');
select is((select count(*)::integer from pg_policies
    where schemaname='storage' and tablename='objects'
        and policyname like 'cce_moderation_avatar_%' and cmd in ('INSERT','UPDATE','DELETE','ALL')),
    0, 'Worker has no Storage mutation policy');
select ok(pg_get_functiondef('ops_private.current_identity()'::regprocedure)
    like '%moderation_worker%', 'Moderation Auth identity is excluded from app actors');
select ok(pg_get_functiondef('ops_private.avatar_storage_access(text,boolean)'::regprocedure)
    like '%moderation_worker%', 'Worker tag disables inherited contributor/Owner Storage reads');
select ok(pg_get_functiondef('ops_private.moderation_avatar_storage_access(text)'::regprocedure)
    like '%auth_worker_user_id%', 'Storage read is bound to the assigned Auth worker');

select * from finish();
rollback;
