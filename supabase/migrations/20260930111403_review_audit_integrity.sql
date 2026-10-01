begin;
set local role cce_migrator;

-- The deferred check sees the feedback and event written later in the same
-- Owner transaction. It does not rely on the API remembering to write them.
create policy migrator_feedback_audit_read on public.submission_feedback
    for select to cce_migrator using (true);
create policy migrator_event_audit_read on ops_private.contribution_events
    for select to cce_migrator using (true);
create function ops_private.require_review_audit() returns trigger
language plpgsql security definer set search_path='' as $$
begin
    if old.status='UNDER_REVIEW'
        and new.status in ('CHANGES_REQUESTED','REJECTED','APPROVED')
        and (not exists(select 1 from public.submission_feedback f
            where f.submission_id=new.id and f.revision_id=new.revision_id
                and f.decision=new.status and f.resulting_version=new.version)
        or not exists(select 1 from ops_private.contribution_events e
            where e.submission_id=new.id and e.revision_id=new.revision_id
                and e.action=new.status and e.resulting_version=new.version)) then
        raise exception 'Review decision requires feedback and event in the same transaction'
            using errcode='23514';
    end if;
    return null;
end;
$$;
revoke all on function ops_private.require_review_audit() from public;
create constraint trigger require_review_audit after update on public.character_submissions
    deferrable initially deferred for each row execute function ops_private.require_review_audit();

-- Request audit, not a claim/execution ledger: even an idempotent request while
-- PENDING or RUNNING is recorded. moderation_attempts tracks actual executions.
create table ops_private.moderation_retry_events (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null references ops_private.moderation_jobs(id),
    actor_user_id uuid not null references public.profiles(user_id),
    previous_state text not null
        check (previous_state in ('PENDING','RUNNING','ERROR','LEGACY_ERROR')),
    previous_attempt_number integer not null check (previous_attempt_number >= 0),
    requested_at timestamptz not null default now()
);
create index moderation_retry_events_job_idx
    on ops_private.moderation_retry_events(job_id,requested_at);
alter table ops_private.moderation_retry_events enable row level security;
alter table ops_private.moderation_retry_events force row level security;
grant insert on ops_private.moderation_retry_events to cce_engine;
create policy owner_moderation_retry_event on ops_private.moderation_retry_events
    for insert to cce_engine with check (
        actor_user_id=nullif(current_setting('cce.actor_id',true),'')::uuid
        and exists(select 1 from ops_private.current_identity() where actor_role='world_owner')
        and exists(select 1 from ops_private.moderation_jobs j where j.id=job_id)
    );

reset role;
commit;
