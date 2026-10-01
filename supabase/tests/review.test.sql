begin;
select plan(15);
select ok(not has_table_privilege('authenticated','public.submission_feedback','SELECT'), 'No Data API feedback reads');
select ok(not has_table_privilege('anon','public.submission_feedback','INSERT'), 'No anonymous feedback writes');
select ok(not has_table_privilege('cce_api','public.submission_feedback','INSERT'), 'Contributors cannot decide');
select ok(not has_table_privilege('cce_engine','public.submission_revisions','UPDATE'), 'Engine cannot rewrite revisions');
select ok(not has_table_privilege('cce_engine','public.submission_feedback','UPDATE'), 'Feedback is append-only');
select ok(not has_table_privilege('cce_engine','ops_private.submission_moderation','UPDATE'), 'Moderation reports are immutable');
select ok(not has_column_privilege('cce_engine','public.character_submissions','definition','UPDATE'), 'Engine cannot replace proposal');
select ok(not has_table_privilege('cce_api','ops_private.submission_moderation','INSERT'), 'Contributors cannot forge moderation');
select ok((select relforcerowsecurity from pg_class where oid='public.submission_feedback'::regclass), 'Feedback FORCE RLS');
select ok((select relforcerowsecurity from pg_class where oid='ops_private.submission_moderation'::regclass), 'Moderation FORCE RLS');
select ok(not pg_has_role('cce_api','cce_engine','MEMBER'), 'API cannot assume engine identity');
select ok(has_function_privilege('cce_engine','ops_private.current_identity()','EXECUTE'), 'Engine can revalidate current actor');
select ok(not pg_has_role('cce_api','cce_migrator','MEMBER')
    and not pg_has_role('cce_engine','cce_migrator','MEMBER')
    and not pg_has_role('cce_worker_cpu','cce_migrator','MEMBER')
    and not pg_has_role('cce_worker_gpu','cce_migrator','MEMBER')
    and not pg_has_role('cce_worker_publisher','cce_migrator','MEMBER')
    and not pg_has_role('cce_worker_maintenance','cce_migrator','MEMBER'),
    'No runtime role can become the migration owner');
select ok(not has_table_privilege('cce_api','ops_private.fixture_approval_policy','UPDATE')
    and not has_table_privilege('cce_engine','ops_private.fixture_approval_policy','UPDATE'),
    'Runtime roles cannot enable synthetic approvals');
select ok(has_function_privilege('cce_engine','ops_private.fixture_approval_allowed()','EXECUTE')
    and not has_function_privilege('cce_api','ops_private.fixture_approval_allowed()','EXECUTE'),
    'Only Owner command role can read the fixture approval gate');
select * from finish();
rollback;
