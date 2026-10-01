begin;
set local role cce_migrator;

-- READY means bytes were verified by the API, not that content moderation passed.
-- The app still verifies Storage bytes before the PENDING -> READY update.
create function ops_private.guard_avatar_status() returns trigger
language plpgsql set search_path='' as $$
begin
    if old.status='READY' and new.status is distinct from old.status then
        raise exception 'Ready avatar status is immutable' using errcode='23514';
    end if;
    return new;
end;
$$;
create trigger guard_avatar_status before update on public.avatar_assets
    for each row execute function ops_private.guard_avatar_status();

-- The active attempt must belong to this job. Deferred checking supports the
-- existing two-way job/attempt reference and transactional fixture cleanup.
alter table ops_private.moderation_attempts
    add constraint moderation_attempts_job_id_id_unique unique(job_id,id);
alter table ops_private.moderation_jobs
    add constraint moderation_jobs_active_attempt_fk
    foreign key(id,active_attempt_id)
    references ops_private.moderation_attempts(job_id,id)
    deferrable initially deferred;
create unique index moderation_attempts_one_running_per_job
    on ops_private.moderation_attempts(job_id) where state='RUNNING';

reset role;
commit;
