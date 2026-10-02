begin;
grant execute on function ops_private.current_identity() to cce_migrator;
set local role cce_migrator;

-- No real-content activation path exists in this milestone. Only the explicitly
-- opted-in, disposable test provisioner enables this separate persistent gate.
create table ops_private.fixture_activation_policy (
    singleton boolean primary key default true check(singleton),
    enabled boolean not null default false
);
insert into ops_private.fixture_activation_policy values(true,false);

create table ops_private.character_capacity (
    singleton boolean primary key default true check(singleton),
    active_limit integer not null default 50 check(active_limit between 0 and 50)
);
insert into ops_private.character_capacity values(true,50);

create table world_private.characters (
    id uuid primary key default gen_random_uuid(),
    person_id uuid not null unique references world_private.people(id),
    submission_id uuid not null unique references public.character_submissions(id),
    active_definition_id uuid not null unique references world_private.character_definitions(id),
    status text not null default 'ACTIVE' check(status in ('ACTIVE','SUSPENDED','ARCHIVED')),
    is_fixture boolean not null check(is_fixture),
    created_by uuid not null references public.profiles(user_id),
    activated_at timestamptz not null default now()
);
create index characters_creator_idx on world_private.characters(created_by);
create index characters_active_idx on world_private.characters(id) where status='ACTIVE';

-- Source-bound, private bootstrap snapshot, not lived experience or an inferred
-- relationship. Runtime mutation/extraction remains the M4/M6 workstream.
create table world_private.character_initial_state (
    character_id uuid primary key references world_private.characters(id) on delete cascade,
    definition_id uuid not null references world_private.character_definitions(id),
    bootstrap jsonb not null check(jsonb_typeof(bootstrap)='object'),
    owner_person_id uuid not null references world_private.people(id),
    owner_relationship_status text not null default 'UNACQUAINTED'
        check(owner_relationship_status='UNACQUAINTED'),
    owner_experience_count integer not null default 0 check(owner_experience_count=0),
    created_at timestamptz not null default now()
);
create index initial_state_definition_idx on world_private.character_initial_state(definition_id);
create index initial_state_owner_idx on world_private.character_initial_state(owner_person_id);

create table ops_private.character_activation_events (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null unique references world_private.characters(id),
    actor_user_id uuid not null references public.profiles(user_id),
    definition_id uuid not null references world_private.character_definitions(id),
    reason text not null check(length(btrim(reason)) between 10 and 1000),
    recorded_at timestamptz not null default now()
);
create index activation_actor_idx on ops_private.character_activation_events(actor_user_id);
create index activation_definition_idx on ops_private.character_activation_events(definition_id);

create table ops_private.character_capacity_events (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null unique,
    actor_user_id uuid not null references public.profiles(user_id),
    previous_limit integer not null check(previous_limit between 0 and 50),
    active_limit integer not null check(active_limit between 0 and 50),
    active_count integer not null check(active_count>=0 and active_count<=active_limit),
    reason text not null check(length(btrim(reason)) between 10 and 1000),
    recorded_at timestamptz not null default now()
);
create index capacity_actor_idx on ops_private.character_capacity_events(actor_user_id);

do $$
declare t text;
begin
    foreach t in array array['ops_private.fixture_activation_policy',
        'ops_private.character_capacity','world_private.characters',
        'world_private.character_initial_state','ops_private.character_activation_events',
        'ops_private.character_capacity_events'] loop
        execute format('alter table %s enable row level security',t);
        execute format('alter table %s force row level security',t);
        execute format('create policy activation_migrator on %s to cce_migrator '
            'using(true) with check(true)',t);
        if t <> 'ops_private.fixture_activation_policy' then
            execute format('grant select on %s to cce_engine',t);
            execute format('create policy activation_owner_read on %s for select to cce_engine '
                'using(exists(select 1 from ops_private.current_identity() '
                'where actor_role=''world_owner''))',t);
        end if;
    end loop;
    -- FORCE RLS applies inside the narrowly scoped definer functions too.
    foreach t in array array['public.character_submissions','public.submission_revisions',
        'public.submission_feedback','ops_private.submission_moderation',
        'world_private.character_definitions','public.avatar_assets'] loop
        execute format('create policy activation_source_read on %s for select '
            'to cce_migrator using(true)',t);
    end loop;
end $$;

create function ops_private.activate_fixture_character(
    source_submission uuid, expected_version integer, source_revision uuid,
    target_definition uuid, expected_hash text, activation_reason text
) returns uuid
language plpgsql security definer set search_path='' as $$
declare
    actor uuid := nullif(current_setting('cce.actor_id',true),'')::uuid;
    owner_person uuid;
    limit_value integer;
    source_row record;
    existing_id uuid;
    new_id uuid;
    new_person uuid;
begin
    select person_id into owner_person from ops_private.current_identity()
        where actor_role='world_owner';
    if not found then raise exception 'World Owner required' using errcode='42501'; end if;
    if not coalesce((select enabled from ops_private.fixture_activation_policy where singleton),false)
        or not ops_private.fixture_approval_allowed() then
        raise exception 'Fixture activation disabled' using errcode='23514';
    end if;
    if length(btrim(activation_reason)) not between 10 and 1000 then
        raise exception 'Activation reason required' using errcode='23514';
    end if;
    -- Global capacity row first, then source submission. All activation/limit
    -- commands use this order; no unlocked count-then-insert race is possible.
    select active_limit into strict limit_value from ops_private.character_capacity
        where singleton for update;
    perform 1 from public.character_submissions where id=source_submission for update;
    select d.id,d.artifact,d.artifact_sha256 into source_row
    from public.character_submissions s
    join world_private.character_definitions d on d.submission_id=s.id
        and d.revision_id=s.revision_id and d.id=target_definition
    join public.submission_revisions r on r.id=s.revision_id and r.submission_id=s.id
    join public.submission_feedback f on f.id=d.approval_id and f.submission_id=s.id
        and f.revision_id=r.id and f.decision='APPROVED' and f.resulting_version=s.version
    join ops_private.submission_moderation m on m.revision_id=r.id
    left join public.avatar_assets a on a.id=r.avatar_id
    where s.id=source_submission and s.status='APPROVED' and s.version=expected_version
        and r.id=source_revision and d.artifact_sha256=expected_hash
        and m.is_fixture and d.artifact->'source'->>'is_fixture'='true'
        and (m.result='PASS' or (m.result='REVIEW' and s.review_accepted))
        and d.artifact->'source'->>'moderation_result'=m.result
        and d.artifact->'proposal'=r.definition
        and d.artifact->'bootstrap'->>'source_revision_id'=r.id::text
        and (r.avatar_id is null or (a.status='READY'
            and d.artifact->'source'->>'avatar_sha256'=a.sha256));
    if not found then raise exception 'Current approved fixture definition required'
        using errcode='23514'; end if;
    select id into existing_id from world_private.characters where submission_id=source_submission;
    if found then
        if not exists(select 1 from world_private.characters where id=existing_id
            and active_definition_id=target_definition) then
            raise exception 'Activation source conflict' using errcode='23514';
        end if;
        return existing_id;
    end if;
    if (select count(*) from world_private.characters where status='ACTIVE')>=limit_value then
        raise exception 'Active character capacity reached' using errcode='23514';
    end if;
    insert into world_private.people(display_name)
        values(source_row.artifact->'proposal'->>'name') returning id into new_person;
    insert into world_private.characters(person_id,submission_id,active_definition_id,is_fixture,created_by)
        values(new_person,source_submission,target_definition,true,actor) returning id into new_id;
    insert into world_private.character_initial_state(character_id,definition_id,bootstrap,owner_person_id)
        values(new_id,target_definition,source_row.artifact->'bootstrap',owner_person);
    insert into ops_private.character_activation_events(character_id,actor_user_id,definition_id,reason)
        values(new_id,actor,target_definition,btrim(activation_reason));
    return new_id;
end $$;
revoke all on function ops_private.activate_fixture_character(uuid,integer,uuid,uuid,text,text)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.activate_fixture_character(uuid,integer,uuid,uuid,text,text)
    to cce_engine;

create function ops_private.set_character_capacity(
    expected_limit integer, new_limit integer, change_reason text, command_id uuid
) returns ops_private.character_capacity_events
language plpgsql security definer set search_path='' as $$
declare
    actor uuid := nullif(current_setting('cce.actor_id',true),'')::uuid;
    old_limit integer;
    count_value integer;
    result ops_private.character_capacity_events;
begin
    if not exists(select 1 from ops_private.current_identity() where actor_role='world_owner') then
        raise exception 'World Owner required' using errcode='42501';
    end if;
    select active_limit into strict old_limit from ops_private.character_capacity
        where singleton for update;
    select * into result from ops_private.character_capacity_events where request_id=command_id;
    if found then
        if result.actor_user_id<>actor or result.previous_limit<>expected_limit
            or result.active_limit<>new_limit or result.reason<>btrim(change_reason) then
            raise exception 'Capacity command conflict' using errcode='23514';
        end if;
        return result;
    end if;
    select count(*) into count_value from world_private.characters where status='ACTIVE';
    if expected_limit<>old_limit or new_limit not between 0 and 50 or new_limit<count_value
        or new_limit=old_limit or length(btrim(change_reason)) not between 10 and 1000 then
        raise exception 'Capacity change conflict' using errcode='23514';
    end if;
    update ops_private.character_capacity set active_limit=new_limit where singleton;
    insert into ops_private.character_capacity_events(
        request_id,actor_user_id,previous_limit,active_limit,active_count,reason)
    values(command_id,actor,old_limit,new_limit,count_value,btrim(change_reason)) returning * into result;
    return result;
end $$;
revoke all on function ops_private.set_character_capacity(integer,integer,text,uuid)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.set_character_capacity(integer,integer,text,uuid) to cce_engine;
reset role;
-- Readiness marker remains writable only by the privileged migration runner.
update ops_private.schema_version set version=6 where singleton;
commit;
