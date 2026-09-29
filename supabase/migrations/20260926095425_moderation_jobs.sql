begin;
set local role cce_migrator;

-- Canonical verdict stays one per revision. Execution attempts are separate and
-- never replace a successful verdict (especially BLOCK).
create table ops_private.moderation_jobs (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null references public.character_submissions(id),
    revision_id uuid not null unique,
    avatar_id uuid references public.avatar_assets(id),
    avatar_sha256 text,
    source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
    state text not null default 'PENDING'
        check (state in ('PENDING','RUNNING','SUCCEEDED','ERROR','CANCELLED')),
    requested_by uuid not null references public.profiles(user_id),
    requested_at timestamptz not null default now(),
    attempt_number integer not null default 0 check (attempt_number >= 0),
    active_attempt_id uuid,
    lease_until timestamptz,
    error_code text,
    foreign key (revision_id,submission_id) references public.submission_revisions(id,submission_id),
    check ((avatar_id is null and avatar_sha256 is null)
        or (avatar_id is not null and avatar_sha256 ~ '^[0-9a-f]{64}$')),
    check ((state='RUNNING' and lease_until is not null and active_attempt_id is not null)
        or (state<>'RUNNING' and lease_until is null))
);
create index moderation_jobs_submission_idx on ops_private.moderation_jobs(submission_id);
create index moderation_jobs_pending_idx on ops_private.moderation_jobs(requested_at,id)
    where state='PENDING';
create index moderation_jobs_expired_idx on ops_private.moderation_jobs(lease_until)
    where state='RUNNING';
create table ops_private.moderation_attempts (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null references ops_private.moderation_jobs(id),
    attempt_number integer not null check (attempt_number > 0),
    state text not null check (state in ('RUNNING','SUCCEEDED','ERROR','CANCELLED')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    error_code text,
    result text check (result in ('PASS','REVIEW','BLOCK','ERROR')),
    provider text,
    policy_version text,
    detail text,
    unique(job_id,attempt_number),
    check ((state='RUNNING' and finished_at is null)
        or (state<>'RUNNING' and finished_at is not null))
);
alter table ops_private.moderation_jobs enable row level security;
alter table ops_private.moderation_jobs force row level security;
alter table ops_private.moderation_attempts enable row level security;
alter table ops_private.moderation_attempts force row level security;
grant select on ops_private.moderation_jobs,ops_private.moderation_attempts to cce_engine;
create policy owner_moderation_jobs_read on ops_private.moderation_jobs for select to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));
create policy owner_moderation_attempts_read on ops_private.moderation_attempts for select to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));
reset role;

-- Narrow private functions are the only worker write surface. They run with
-- migration authority; workers never receive table access or submission writes.
create function ops_private.enqueue_moderation(target_submission uuid, target_revision uuid)
returns uuid language plpgsql security definer set search_path='' as $$
declare
    source_row record;
    existing ops_private.moderation_jobs%rowtype;
    verdict text;
    created_job uuid;
begin
    if not exists(select 1 from ops_private.current_identity() where actor_role='world_owner') then
        raise exception 'World Owner required' using errcode='42501';
    end if;
    select s.id,r.id as revision_id,r.definition,r.avatar_id,a.sha256 into source_row
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
        if existing.state in ('PENDING','RUNNING') then
            return existing.id;
        end if;
        if existing.state<>'ERROR' then
            raise exception 'Only errored jobs can be retried' using errcode='23514';
        end if;
        update ops_private.moderation_jobs set state='PENDING',error_code=null,
            requested_by=nullif(current_setting('cce.actor_id',true),'')::uuid,
            requested_at=now() where id=existing.id;
        return existing.id;
    end if;
    insert into ops_private.moderation_jobs(submission_id,revision_id,avatar_id,avatar_sha256,
        source_sha256,requested_by)
    values (target_submission,target_revision,source_row.avatar_id,source_row.sha256,
        encode(sha256(convert_to(source_row.definition::text,'UTF8')),'hex'),
        nullif(current_setting('cce.actor_id',true),'')::uuid) returning id into created_job;
    -- Preserve legacy unconfigured ERROR before a later successful retry replaces
    -- the canonical snapshot. New errors live exclusively in the attempt ledger.
    if verdict='ERROR' then
        insert into ops_private.moderation_attempts(job_id,attempt_number,state,finished_at,
            error_code,result,provider,policy_version,detail)
        select created_job,1,'ERROR',now(),'LEGACY_ERROR',result,provider,policy_version,detail
        from ops_private.submission_moderation where revision_id=target_revision;
        update ops_private.moderation_jobs set attempt_number=1 where id=created_job;
    end if;
    return created_job;
end;
$$;

create function ops_private.claim_moderation()
returns jsonb language plpgsql security definer set search_path='' as $$
declare
    job ops_private.moderation_jobs%rowtype;
    attempt uuid;
    source_row record;
begin
    -- Expired work is visible as ERROR, never implicitly successful. Owner retry
    -- creates a new attempt; a late result cannot finish the expired one.
    for job in select * from ops_private.moderation_jobs where state='RUNNING'
        and lease_until<=clock_timestamp() for update skip locked loop
        update ops_private.moderation_attempts set state='ERROR',finished_at=now(),
            error_code='LEASE_EXPIRED' where id=job.active_attempt_id and state='RUNNING';
        update ops_private.moderation_jobs set state='ERROR',lease_until=null,
            error_code='LEASE_EXPIRED' where id=job.id;
    end loop;
    for job in select * from ops_private.moderation_jobs where state='PENDING'
        order by requested_at,id for update skip locked loop
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

create function ops_private.finish_moderation(
    target_job uuid, target_attempt uuid, target_source_sha256 text,
    target_avatar_sha256 text, verdict text, model_provider text,
    model_policy_version text, result_detail text, failure_code text
) returns boolean language plpgsql security definer set search_path='' as $$
declare
    job ops_private.moderation_jobs%rowtype;
    target_submission uuid;
    source_row record;
begin
    -- Same submission -> job lock order as enqueue; claim never locks submissions.
    select submission_id into target_submission from ops_private.moderation_jobs where id=target_job;
    perform 1 from public.character_submissions where id=target_submission for update;
    select * into job from ops_private.moderation_jobs where id=target_job for update;
    if not found or job.state<>'RUNNING' or job.active_attempt_id<>target_attempt
        or job.lease_until<=clock_timestamp() then
        return false;
    end if;
    if target_source_sha256 is distinct from job.source_sha256
        or target_avatar_sha256 is distinct from job.avatar_sha256 then
        raise exception 'Scan source mismatch' using errcode='23514';
    end if;
    if verdict is null or verdict not in ('PASS','REVIEW','BLOCK','ERROR')
        or model_provider is null or length(model_provider) not between 1 and 100
        or model_policy_version is null or length(model_policy_version) not between 1 and 100
        or result_detail is null or length(result_detail) not between 1 and 1000
        or (verdict='ERROR' and (failure_code is null or failure_code not in
            ('MODEL_UNAVAILABLE','MODEL_TIMEOUT','INVALID_OUTPUT','AVATAR_UNAVAILABLE','SCAN_FAILED')))
        or (verdict<>'ERROR' and failure_code is not null) then
        raise exception 'Invalid moderation outcome' using errcode='23514';
    end if;
    select s.id into source_row from public.character_submissions s
        join public.submission_revisions r on r.id=s.revision_id and r.submission_id=s.id
        left join public.avatar_assets a on a.id=r.avatar_id and a.status='READY'
        where s.id=job.submission_id and s.status='UNDER_REVIEW' and r.id=job.revision_id
            and r.avatar_id is not distinct from job.avatar_id
            and a.sha256 is not distinct from job.avatar_sha256
            and encode(sha256(convert_to(r.definition::text,'UTF8')),'hex')=job.source_sha256;
    if not found then
        update ops_private.moderation_attempts set state='CANCELLED',finished_at=now(),
            error_code='SOURCE_CHANGED' where id=target_attempt;
        update ops_private.moderation_jobs set state='CANCELLED',lease_until=null,
            error_code='SOURCE_CHANGED' where id=job.id;
        return false;
    end if;
    if verdict<>'ERROR' then
        insert into ops_private.submission_moderation
            (revision_id,submission_id,result,provider,policy_version,is_fixture,detail)
        values (job.revision_id,job.submission_id,verdict,model_provider,model_policy_version,false,result_detail)
        on conflict(revision_id) do update set result=excluded.result,provider=excluded.provider,
            policy_version=excluded.policy_version,is_fixture=false,detail=excluded.detail,created_at=now()
            where submission_moderation.result='ERROR';
        if not found then
            raise exception 'Successful verdict is immutable' using errcode='23514';
        end if;
    end if;
    update ops_private.moderation_attempts set state=case when verdict='ERROR' then 'ERROR' else 'SUCCEEDED' end,
        finished_at=now(),error_code=failure_code,result=verdict,provider=model_provider,
        policy_version=model_policy_version,detail=result_detail where id=target_attempt;
    update ops_private.moderation_jobs set state=case when verdict='ERROR' then 'ERROR' else 'SUCCEEDED' end,
        lease_until=null,error_code=failure_code where id=job.id;
    return true;
end;
$$;
revoke all on function ops_private.enqueue_moderation(uuid,uuid),
    ops_private.claim_moderation(),
    ops_private.finish_moderation(uuid,uuid,text,text,text,text,text,text,text)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.enqueue_moderation(uuid,uuid) to cce_engine;
grant execute on function ops_private.claim_moderation(),
    ops_private.finish_moderation(uuid,uuid,text,text,text,text,text,text,text) to cce_worker_cpu;
commit;
