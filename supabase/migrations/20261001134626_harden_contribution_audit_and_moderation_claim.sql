begin;
set local role cce_migrator;

-- The shared action CHECK also contains Owner actions. Ownership alone must
-- not permit a contributor to impersonate those actions in the audit ledger.
alter policy own_contribution_event on ops_private.contribution_events
    with check (
        action in ('CREATED','SAVE','SUBMIT','WITHDRAW','REVISE')
        and actor_user_id=nullif((select current_setting('cce.actor_id',true)),'')::uuid
        and exists(select 1 from public.character_submissions s where s.id=submission_id
            and s.version=resulting_version)
    );
reset role;

create or replace function ops_private.claim_moderation()
returns jsonb language plpgsql security definer set search_path='' as $$
declare
    job ops_private.moderation_jobs%rowtype;
    attempt uuid;
    source_row record;
    ledger_attempt_number integer;
begin
    for job in select * from ops_private.moderation_jobs where state='RUNNING'
        and lease_until<=clock_timestamp() for update skip locked loop
        update ops_private.moderation_attempts set state='ERROR',finished_at=now(),
            error_code='LEASE_EXPIRED' where id=job.active_attempt_id and state='RUNNING';
        update ops_private.moderation_jobs set state='ERROR',lease_until=null,
            error_code='LEASE_EXPIRED' where id=job.id;
    end loop;
    for job in select * from ops_private.moderation_jobs where state='PENDING'
        order by requested_at,id for update skip locked loop
        -- Legitimate attempt writers hold this job lock. A pending job must
        -- have neither a live attempt nor a ledger ahead of its counter.
        -- Preserve the ledger, end orphaned work visibly, and let Owner retry
        -- from its highest recorded number instead of stalling the queue.
        select coalesce(max(attempt_number),0) into ledger_attempt_number
            from ops_private.moderation_attempts where job_id=job.id;
        if ledger_attempt_number>job.attempt_number or exists(
            select 1 from ops_private.moderation_attempts
                where job_id=job.id and state='RUNNING'
        ) then
            update ops_private.moderation_attempts set state='ERROR',finished_at=now(),
                error_code='JOB_INCONSISTENT' where job_id=job.id and state='RUNNING';
            update ops_private.moderation_jobs set state='ERROR',lease_until=null,
                error_code='JOB_INCONSISTENT',
                attempt_number=greatest(job.attempt_number,ledger_attempt_number)
                where id=job.id;
            continue;
        end if;
        select r.definition,r.avatar_id,a.sha256 into source_row
        from public.character_submissions s
        join public.submission_revisions r on r.id=s.revision_id and r.submission_id=s.id
        left join public.avatar_assets a on a.id=r.avatar_id and a.status='READY'
        where s.id=job.submission_id and s.status='UNDER_REVIEW' and r.id=job.revision_id;
        if not found or source_row.avatar_id is distinct from job.avatar_id
            or source_row.sha256 is distinct from job.avatar_sha256
            or encode(sha256(convert_to(source_row.definition::text,'UTF8')),'hex')<>job.source_sha256 then
            update ops_private.moderation_jobs set state='CANCELLED',error_code='SOURCE_CHANGED'
                where id=job.id;
            continue;
        end if;
        insert into ops_private.moderation_attempts(job_id,attempt_number,state)
            values (job.id,job.attempt_number+1,'RUNNING') returning id into attempt;
        update ops_private.moderation_jobs set state='RUNNING',active_attempt_id=attempt,
            attempt_number=attempt_number+1,lease_until=clock_timestamp()+interval '5 minutes'
            where id=job.id;
        return jsonb_build_object('job_id',job.id,'attempt_id',attempt,
            'revision_id',job.revision_id,'source_sha256',job.source_sha256,
            'definition',source_row.definition,'avatar_id',job.avatar_id,
            'avatar_sha256',job.avatar_sha256);
    end loop;
    return null;
end;
$$;

-- Require both security boundaries before accepting API traffic. The marker
-- is deliberately written only by the privileged migration runner.
do $$
begin
    if (select version from ops_private.schema_version where singleton) is distinct from 3 then
        raise exception 'Expected CCE schema version 3 before audit and claim hardening';
    end if;
    update ops_private.schema_version set version=4 where singleton;
end;
$$;
commit;
