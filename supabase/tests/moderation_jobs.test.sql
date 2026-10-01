begin;
select plan(12);
select ok(not has_table_privilege('authenticated','ops_private.moderation_jobs','SELECT'), 'No Data API job reads');
select ok(not has_table_privilege('cce_api','ops_private.moderation_attempts','SELECT'), 'No contributor attempt reads');
select ok(not has_table_privilege('cce_engine','ops_private.moderation_attempts','UPDATE'), 'Owner cannot rewrite attempts');
select ok(not has_table_privilege('cce_worker_cpu','ops_private.moderation_jobs','UPDATE'), 'Worker has function-only writes');
select ok(not has_function_privilege('authenticated','ops_private.claim_moderation()','EXECUTE'), 'No Data API claim');
select ok(not has_function_privilege('cce_api','ops_private.claim_moderation()','EXECUTE'), 'No contributor claim');
select ok(not has_function_privilege('cce_worker_cpu','ops_private.enqueue_moderation(uuid,uuid)','EXECUTE'), 'Worker cannot enqueue');
select ok(has_function_privilege('cce_worker_cpu','ops_private.claim_moderation()','EXECUTE'), 'CPU worker can claim');
select ok((select relforcerowsecurity from pg_class where oid='ops_private.moderation_jobs'::regclass), 'Jobs FORCE RLS');
select ok((select relforcerowsecurity from pg_class where oid='ops_private.moderation_attempts'::regclass), 'Attempts FORCE RLS');
select ok((select count(*) from pg_constraint where conrelid='ops_private.moderation_jobs'::regclass
    and conname='moderation_jobs_active_attempt_fk' and contype='f')=1,
    'Active attempt belongs to its job');
select ok((select count(*) from pg_indexes where schemaname='ops_private'
    and indexname='moderation_attempts_one_running_per_job')=1,
    'Only one running attempt per job');
select * from finish();
rollback;
