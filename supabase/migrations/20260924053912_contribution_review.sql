begin;
grant execute on function ops_private.current_identity() to cce_engine;
set local role cce_migrator;

alter table public.character_submissions drop constraint character_submissions_status_check;
alter table public.character_submissions drop constraint character_submissions_check;
alter table public.character_submissions add constraint submission_status_check check (
    status in ('DRAFT','SUBMITTED','UNDER_REVIEW','CHANGES_REQUESTED','REJECTED','APPROVED','WITHDRAWN')
);
alter table public.character_submissions add constraint submission_revision_required check (
    status='DRAFT' or revision_id is not null
);
alter table public.character_submissions add column review_accepted boolean not null default false;
create index submissions_review_queue_idx on public.character_submissions(status, updated_at desc);
alter table ops_private.contribution_events drop constraint contribution_events_action_check;
alter table ops_private.contribution_events add constraint contribution_event_action_check check (
    action in ('CREATED','SAVE','SUBMIT','WITHDRAW','REVISE','START_REVIEW',
        'CHANGES_REQUESTED','REJECTED','APPROVED')
);
alter table ops_private.contribution_events add column reason text
    check (reason is null or length(btrim(reason)) between 1 and 2000);

create table public.submission_feedback (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null references public.character_submissions(id),
    revision_id uuid not null,
    actor_user_id uuid not null references public.profiles(user_id),
    decision text not null check (decision in ('CHANGES_REQUESTED','REJECTED','APPROVED')),
    reason text not null check (length(btrim(reason)) between 1 and 2000),
    resulting_version integer not null check (resulting_version > 0),
    created_at timestamptz not null default now(),
    unique(submission_id, resulting_version),
    foreign key (revision_id, submission_id) references public.submission_revisions(id, submission_id)
);
create index submission_feedback_revision_idx on public.submission_feedback(revision_id, submission_id);
create index submission_feedback_actor_idx on public.submission_feedback(actor_user_id);
create table ops_private.submission_moderation (
    revision_id uuid primary key,
    submission_id uuid not null references public.character_submissions(id),
    result text not null check (result in ('PASS','REVIEW','BLOCK','ERROR')),
    provider text not null check (length(provider) between 1 and 100),
    policy_version text not null check (length(policy_version) between 1 and 100),
    is_fixture boolean not null,
    detail text not null check (length(detail) between 1 and 1000),
    created_at timestamptz not null default now(),
    foreign key (revision_id, submission_id) references public.submission_revisions(id, submission_id)
);
create index submission_moderation_submission_idx on ops_private.submission_moderation(submission_id);
alter table public.submission_feedback enable row level security;
alter table public.submission_feedback force row level security;
alter table ops_private.submission_moderation enable row level security;
alter table ops_private.submission_moderation force row level security;

grant select on public.character_submissions, public.submission_revisions to cce_engine;
grant update (status, version, updated_at, review_accepted) on public.character_submissions to cce_engine;
grant select on public.submission_feedback to cce_api, cce_engine;
grant insert on public.submission_feedback, ops_private.contribution_events to cce_engine;
grant select, insert on ops_private.submission_moderation to cce_engine;
create policy owner_submission on public.character_submissions to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'))
    with check (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));
create policy owner_revision on public.submission_revisions for select to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));
create policy readable_feedback on public.submission_feedback for select to cce_api, cce_engine
    using (exists(select 1 from public.character_submissions s where s.id=submission_id));
create policy owner_feedback on public.submission_feedback for insert to cce_engine
    with check (actor_user_id=nullif((select current_setting('cce.actor_id',true)),'')::uuid
        and exists(select 1 from public.character_submissions s where s.id=submission_id
            and s.revision_id=submission_feedback.revision_id and s.status=decision
            and s.version=resulting_version));
create policy owner_moderation on ops_private.submission_moderation to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'))
    with check (exists(select 1 from public.character_submissions s where s.id=submission_id
        and s.revision_id=submission_moderation.revision_id and s.status='SUBMITTED'));
create policy owner_contribution_event on ops_private.contribution_events for insert to cce_engine
    with check (actor_user_id=nullif((select current_setting('cce.actor_id',true)),'')::uuid
        and exists(select 1 from public.character_submissions s where s.id=submission_id
            and s.version=resulting_version));

create or replace function ops_private.guard_submission_transition() returns trigger
language plpgsql set search_path = '' as $$
begin
    if tg_op='INSERT' then
        if new.status<>'DRAFT' or new.version<>1 or new.revision_id is not null
            or new.review_accepted then
            raise exception 'New submissions must be drafts' using errcode='23514';
        end if;
        return new;
    end if;
    if new.user_id<>old.user_id or new.creation_key<>old.creation_key
        or new.created_at<>old.created_at or new.id<>old.id or new.version<>old.version+1 then
        raise exception 'Invalid submission identity or version' using errcode='23514';
    end if;
    if current_user='cce_api' then
        if not (
            (old.status='DRAFT' and new.status='DRAFT' and new.revision_id is not distinct from old.revision_id)
            or (old.status='DRAFT' and new.status='SUBMITTED' and new.revision_id is distinct from old.revision_id)
            or (old.status='CHANGES_REQUESTED' and new.status='DRAFT' and new.definition=old.definition
                and new.revision_id=old.revision_id)
            or (old.status in ('SUBMITTED','UNDER_REVIEW','CHANGES_REQUESTED') and new.status='WITHDRAWN'
                and new.definition=old.definition and new.revision_id=old.revision_id)
        ) or new.review_accepted<>old.review_accepted then
            raise exception 'Invalid contributor transition' using errcode='23514';
        end if;
    elsif current_user='cce_engine' then
        if not ((old.status='SUBMITTED' and new.status='UNDER_REVIEW')
            or (old.status='UNDER_REVIEW' and new.status in ('CHANGES_REQUESTED','REJECTED','APPROVED')))
            or new.definition<>old.definition or new.revision_id<>old.revision_id
            or not exists(select 1 from ops_private.current_identity() where actor_role='world_owner') then
            raise exception 'Invalid Owner transition' using errcode='23514';
        end if;
        if new.status='APPROVED' and not exists (
            select 1 from ops_private.submission_moderation m where m.revision_id=new.revision_id
            and (m.result='PASS' or (m.result='REVIEW' and new.review_accepted))
        ) then
            raise exception 'Moderation approval required' using errcode='23514';
        end if;
        if new.status<>'APPROVED' and new.review_accepted<>old.review_accepted then
            raise exception 'Review acceptance only on approval' using errcode='23514';
        end if;
    else
        raise exception 'Unsupported submission writer' using errcode='42501';
    end if;
    if new.status='SUBMITTED' and not exists(select 1 from public.submission_revisions r
        where r.id=new.revision_id and r.submission_id=new.id and r.definition=new.definition) then
        raise exception 'Submission must match immutable revision' using errcode='23514';
    end if;
    new.updated_at := now();
    return new;
end;
$$;
reset role;
commit;
