begin;
set local role cce_migrator;

-- The audit checker already gives this role the same SELECT scope.
drop policy activation_source_read on public.submission_feedback;
grant update (review_accepted) on public.character_submissions to cce_api;

-- The contributor role never receives direct access to private character data.
create function ops_private.fixture_revision_allowed(source_submission uuid, proposed jsonb default null)
returns boolean language sql stable security definer set search_path='' as $$
    select exists (
        select 1 from world_private.characters c
        join world_private.character_definitions d on d.id=c.active_definition_id
        join public.character_submissions s on s.id=c.submission_id
        where c.submission_id=source_submission and c.is_fixture
            and s.user_id=nullif(current_setting('cce.actor_id',true),'')::uuid
            and exists(select 1 from ops_private.current_identity())
            and (proposed is null or
                proposed - array['introduction','speech_style','humor']::text[]
                = (d.artifact->'proposal') - array['introduction','speech_style','humor']::text[])
    )
$$;
revoke all on function ops_private.fixture_revision_allowed(uuid,jsonb)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.fixture_revision_allowed(uuid,jsonb) to cce_api;

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
            or (old.status='APPROVED' and new.status='DRAFT' and new.definition=old.definition
                and new.revision_id=old.revision_id and new.review_accepted=false
                and ops_private.fixture_revision_allowed(old.id))
            or (old.status in ('SUBMITTED','UNDER_REVIEW','CHANGES_REQUESTED') and new.status='WITHDRAWN'
                and new.definition=old.definition and new.revision_id=old.revision_id)
        ) or (new.review_accepted<>old.review_accepted and not
            (old.status='APPROVED' and new.status='DRAFT' and new.review_accepted=false)) then
            raise exception 'Invalid contributor transition' using errcode='23514';
        end if;
        -- Ordinary revisions cannot rewrite the fixed MVP personality,
        -- drives, baseline or backstory. Corrections use a separate audit path.
        if new.status='SUBMITTED' and not
            ops_private.fixture_revision_allowed(new.id,new.definition)
            and exists(select 1 from public.submission_feedback f
                where f.submission_id=new.id and f.decision='APPROVED') then
            raise exception 'Normal revision changes fixed character core' using errcode='23514';
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

-- A pending/rejected candidate never invalidates the last approved, active
-- source. Its immutable approval, moderation and artifact remain independently
-- verifiable. The original bootstrap snapshot is deliberately NOT replaced.
create or replace function ops_private.current_fixture_character_source(target_character uuid)
returns boolean language sql stable security definer set search_path='' as $$
    select exists(
        select 1 from world_private.characters c
        join world_private.character_initial_state i on i.character_id=c.id
        join world_private.character_definitions d on d.id=c.active_definition_id
            and d.submission_id=c.submission_id
        join public.submission_revisions r on r.id=d.revision_id and r.submission_id=c.submission_id
        join public.submission_feedback f on f.id=d.approval_id and f.submission_id=c.submission_id
            and f.revision_id=r.id and f.decision='APPROVED'
        join ops_private.submission_moderation m on m.revision_id=r.id
        left join public.avatar_assets a on a.id=r.avatar_id
        where c.id=target_character and c.is_fixture and m.is_fixture
            and d.artifact->'source'->>'is_fixture'='true'
            and m.result in ('PASS','REVIEW')
            and d.artifact->'source'->>'moderation_result'=m.result
            and d.artifact->'proposal'=r.definition
            and d.artifact->'bootstrap'->>'source_revision_id'=r.id::text
            and (r.avatar_id is null or (a.status='READY'
                and d.artifact->'source'->>'avatar_sha256'=a.sha256))
    ) and coalesce((select enabled from ops_private.fixture_activation_policy where singleton),false)
      and ops_private.fixture_approval_allowed()
$$;

create table ops_private.character_definition_events (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null unique,
    character_id uuid not null references world_private.characters(id),
    actor_user_id uuid not null references public.profiles(user_id),
    previous_definition_id uuid not null references world_private.character_definitions(id),
    definition_id uuid not null references world_private.character_definitions(id),
    previous_version integer not null check(previous_version>0),
    new_version integer not null check(new_version=previous_version+1),
    reason text not null check(length(btrim(reason)) between 10 and 1000),
    recorded_at timestamptz not null default now(),
    check(previous_definition_id<>definition_id)
);
create index character_definition_events_character_idx
    on ops_private.character_definition_events(character_id,recorded_at desc,id);
create index character_definition_events_actor_idx
    on ops_private.character_definition_events(actor_user_id);
create index character_definition_events_definition_idx
    on ops_private.character_definition_events(definition_id);
alter table ops_private.character_definition_events enable row level security;
alter table ops_private.character_definition_events force row level security;
create policy definition_event_migrator on ops_private.character_definition_events
    to cce_migrator using(true) with check(true);
grant select on ops_private.character_definition_events to cce_engine;
create policy definition_event_owner_read on ops_private.character_definition_events
    for select to cce_engine
    using(exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));

create function ops_private.adopt_fixture_character_definition(
    target_character uuid, target_definition uuid, expected_version integer,
    adoption_reason text, command_id uuid
) returns ops_private.character_definition_events
language plpgsql security definer set search_path='' as $$
declare
    actor uuid := nullif(current_setting('cce.actor_id',true),'')::uuid;
    current_row world_private.characters;
    candidate world_private.character_definitions;
    recorded ops_private.character_definition_events;
    normalized_reason text := btrim(adoption_reason);
begin
    if not exists(select 1 from ops_private.current_identity() where actor_role='world_owner') then
        raise exception 'World Owner required' using errcode='42501';
    end if;
    if length(normalized_reason) not between 10 and 1000 or command_id is null then
        raise exception 'Invalid definition command' using errcode='23514';
    end if;
    select * into current_row from world_private.characters where id=target_character for update;
    if not found or not current_row.is_fixture then
        raise exception 'Fixture character not found' using errcode='23514';
    end if;
    select * into recorded from ops_private.character_definition_events where request_id=command_id;
    if found then
        if recorded.character_id<>target_character or recorded.actor_user_id<>actor
            or recorded.definition_id<>target_definition or recorded.previous_version<>expected_version
            or recorded.reason<>normalized_reason then
            raise exception 'Definition command conflict' using errcode='23514';
        end if;
        return recorded;
    end if;
    if current_row.lifecycle_version<>expected_version
        or current_row.active_definition_id=target_definition
        or not ops_private.current_fixture_character_source(target_character) then
        raise exception 'Character definition changed' using errcode='23514';
    end if;
    select * into candidate from world_private.character_definitions where id=target_definition;
    if not found or candidate.submission_id<>current_row.submission_id
        or candidate.definition_version <=
            (select definition_version from world_private.character_definitions
                where id=current_row.active_definition_id)
        or ((candidate.artifact->'proposal')
            - array['introduction','speech_style','humor']::text[])
            is distinct from ((select artifact->'proposal' from world_private.character_definitions
                where id=current_row.active_definition_id)
            - array['introduction','speech_style','humor']::text[])
        or not exists (
            select 1 from public.character_submissions s
            join public.submission_feedback f on f.id=candidate.approval_id
                and f.submission_id=s.id and f.revision_id=candidate.revision_id
                and f.decision='APPROVED' and f.resulting_version=s.version
            join ops_private.submission_moderation m on m.revision_id=candidate.revision_id
            where s.id=current_row.submission_id and s.status='APPROVED'
                and s.revision_id=candidate.revision_id and m.is_fixture
                and (m.result='PASS' or (m.result='REVIEW' and s.review_accepted))
        ) then
        raise exception 'Current approved normal revision required' using errcode='23514';
    end if;
    update world_private.characters set active_definition_id=target_definition,
        lifecycle_version=lifecycle_version+1,updated_at=now() where id=target_character;
    insert into ops_private.character_definition_events(
        request_id,character_id,actor_user_id,previous_definition_id,definition_id,
        previous_version,new_version,reason)
    values(command_id,target_character,actor,current_row.active_definition_id,target_definition,
        current_row.lifecycle_version,current_row.lifecycle_version+1,normalized_reason)
    returning * into recorded;
    return recorded;
end $$;
revoke all on function ops_private.adopt_fixture_character_definition(uuid,uuid,integer,text,uuid)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.adopt_fixture_character_definition(uuid,uuid,integer,text,uuid)
    to cce_engine;

reset role;
update ops_private.schema_version set version=8 where singleton;
commit;
