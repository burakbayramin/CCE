begin;
set local role cce_migrator;

revoke insert on ops_private.moderation_retry_events from cce_engine;
drop policy owner_moderation_retry_event on ops_private.moderation_retry_events;
grant select on ops_private.moderation_retry_events to cce_engine;
create policy owner_moderation_retry_event_read on ops_private.moderation_retry_events
    for select to cce_engine using (
        exists(select 1 from ops_private.current_identity() where actor_role='world_owner')
    );
create index moderation_retry_events_actor_idx
    on ops_private.moderation_retry_events(actor_user_id);
reset role;

-- Both retry mutation and audit live in the sole enqueue write surface.
-- Existing PENDING/RUNNING calls remain auditable idempotent requests, not
-- new executions. The API supplies neither an asserted state nor an actor ID.
create or replace function ops_private.enqueue_moderation(target_submission uuid, target_revision uuid)
returns uuid language plpgsql security definer set search_path='' as $$
declare
    source_row record;
    existing ops_private.moderation_jobs%rowtype;
    verdict text;
    created_job uuid;
    actor_id uuid;
begin
    if not exists(select 1 from ops_private.current_identity() where actor_role='world_owner') then
        raise exception 'World Owner required' using errcode='42501';
    end if;
    actor_id := nullif(current_setting('cce.actor_id',true),'')::uuid;
    select s.id,s.status,r.id as revision_id,r.definition,r.avatar_id,a.sha256 into source_row
    from public.character_submissions s
    join public.submission_revisions r on r.id=s.revision_id and r.submission_id=s.id
    left join public.avatar_assets a on a.id=r.avatar_id and a.status='READY'
    where s.id=target_submission and r.id=target_revision
        and s.status in ('SUBMITTED','UNDER_REVIEW') for update of s;
    if not found or (source_row.avatar_id is not null and source_row.sha256 is null) then
        raise exception 'Current submitted source required' using errcode='23514';
    end if;
    select result into verdict from ops_private.submission_moderation
        where revision_id=target_revision;
    if verdict is not null and verdict<>'ERROR' then
        raise exception 'A successful verdict cannot be retried' using errcode='23514';
    end if;
    select * into existing from ops_private.moderation_jobs where revision_id=target_revision
        for update;
    if found then
        if existing.state not in ('PENDING','RUNNING','ERROR') then
            raise exception 'Only errored or in-flight jobs can be retried' using errcode='23514';
        end if;
        insert into ops_private.moderation_retry_events
            (job_id,actor_user_id,previous_state,previous_attempt_number)
        values (existing.id,actor_id,existing.state,existing.attempt_number);
        if existing.state in ('PENDING','RUNNING') then
            return existing.id;
        end if;
        update ops_private.moderation_jobs set state='PENDING',error_code=null,
            requested_by=actor_id,requested_at=now() where id=existing.id;
        return existing.id;
    end if;
    if source_row.status='UNDER_REVIEW' and verdict is distinct from 'ERROR' then
        raise exception 'Retry requires an existing job or a legacy error' using errcode='23514';
    end if;
    insert into ops_private.moderation_jobs(submission_id,revision_id,avatar_id,avatar_sha256,
        source_sha256,requested_by)
    values (target_submission,target_revision,source_row.avatar_id,source_row.sha256,
        encode(sha256(convert_to(source_row.definition::text,'UTF8')),'hex'),actor_id)
        returning id into created_job;
    if verdict='ERROR' then
        insert into ops_private.moderation_attempts(job_id,attempt_number,state,finished_at,
            error_code,result,provider,policy_version,detail)
        select created_job,1,'ERROR',now(),'LEGACY_ERROR',result,provider,policy_version,detail
        from ops_private.submission_moderation where revision_id=target_revision;
        update ops_private.moderation_jobs set attempt_number=1 where id=created_job;
        insert into ops_private.moderation_retry_events
            (job_id,actor_user_id,previous_state,previous_attempt_number)
        values (created_job,actor_id,'LEGACY_ERROR',0);
    end if;
    return created_job;
end;
$$;

do $$
begin
    if (select version from ops_private.schema_version where singleton) is distinct from 4 then
        raise exception 'Expected CCE schema version 4 before atomic retry audit';
    end if;
    update ops_private.schema_version set version=5 where singleton;
end;
$$;
commit;
