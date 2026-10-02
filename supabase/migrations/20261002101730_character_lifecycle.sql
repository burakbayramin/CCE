begin;
set local role cce_migrator;

alter table world_private.characters
    add column lifecycle_version integer not null default 1 check(lifecycle_version > 0),
    add column updated_at timestamptz not null default now(),
    add column suspension_reason text,
    add column archive_reason text,
    add constraint character_lifecycle_reasons check (
        (status='ACTIVE' and suspension_reason is null and archive_reason is null)
        or (status='SUSPENDED' and suspension_reason is not null and archive_reason is null)
        or (status='ARCHIVED' and archive_reason is not null)
    );

create table ops_private.character_lifecycle_events (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null unique,
    character_id uuid not null references world_private.characters(id),
    actor_user_id uuid not null references public.profiles(user_id),
    action text not null check(action in ('SUSPEND','ARCHIVE','RESTORE','REACTIVATE')),
    previous_status text not null check(previous_status in ('ACTIVE','SUSPENDED','ARCHIVED')),
    new_status text not null check(new_status in ('ACTIVE','SUSPENDED','ARCHIVED')),
    previous_version integer not null check(previous_version>0),
    new_version integer not null check(new_version=previous_version+1),
    definition_id uuid not null references world_private.character_definitions(id),
    reason text not null check(length(btrim(reason)) between 10 and 1000),
    reviewed_prior_reason text,
    recorded_at timestamptz not null default now()
);
create index character_lifecycle_events_character_idx
    on ops_private.character_lifecycle_events(character_id,recorded_at desc,id);
create index character_lifecycle_events_actor_idx
    on ops_private.character_lifecycle_events(actor_user_id);
create index character_lifecycle_events_definition_idx
    on ops_private.character_lifecycle_events(definition_id);
alter table ops_private.character_lifecycle_events enable row level security;
alter table ops_private.character_lifecycle_events force row level security;
create policy lifecycle_migrator on ops_private.character_lifecycle_events to cce_migrator
    using(true) with check(true);
grant select on ops_private.character_lifecycle_events to cce_engine;
create policy lifecycle_owner_read on ops_private.character_lifecycle_events for select to cce_engine
    using(exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));

-- There are no character-bound M4 jobs yet. The lifecycle_version is the future
-- generation epoch: every M4 producer/committer must pin and recheck it.
create function ops_private.current_fixture_character_source(target_character uuid)
returns boolean language sql stable security definer set search_path='' as $$
    select exists(
        select 1 from world_private.characters c
        join world_private.character_initial_state i on i.character_id=c.id
            and i.definition_id=c.active_definition_id
        join world_private.character_definitions d on d.id=c.active_definition_id
            and d.submission_id=c.submission_id
        join public.character_submissions s on s.id=c.submission_id
            and s.revision_id=d.revision_id
        join public.submission_revisions r on r.id=d.revision_id and r.submission_id=s.id
        join public.submission_feedback f on f.id=d.approval_id and f.submission_id=s.id
            and f.revision_id=r.id and f.decision='APPROVED' and f.resulting_version=s.version
        join ops_private.submission_moderation m on m.revision_id=r.id
        left join public.avatar_assets a on a.id=r.avatar_id
        where c.id=target_character and c.is_fixture and s.status='APPROVED'
            and m.is_fixture and d.artifact->'source'->>'is_fixture'='true'
            and (m.result='PASS' or (m.result='REVIEW' and s.review_accepted))
            and d.artifact->'source'->>'moderation_result'=m.result
            and d.artifact->'proposal'=r.definition
            and d.artifact->'bootstrap'->>'source_revision_id'=r.id::text
            and (r.avatar_id is null or (a.status='READY'
                and d.artifact->'source'->>'avatar_sha256'=a.sha256))
    ) and coalesce((select enabled from ops_private.fixture_activation_policy where singleton),false)
      and ops_private.fixture_approval_allowed()
$$;
revoke all on function ops_private.current_fixture_character_source(uuid)
    from public,anon,authenticated,service_role;

create function ops_private.apply_fixture_character_lifecycle(
    target_character uuid, requested_action text, expected_version integer,
    change_reason text, command_id uuid, reviewed_reason text default null
) returns ops_private.character_lifecycle_events
language plpgsql security definer set search_path='' as $$
declare
    actor uuid := nullif(current_setting('cce.actor_id',true),'')::uuid;
    current_row world_private.characters;
    recorded ops_private.character_lifecycle_events;
    capacity_limit integer;
    next_status text;
    normalized_reason text := btrim(change_reason);
begin
    if not exists(select 1 from ops_private.current_identity() where actor_role='world_owner') then
        raise exception 'World Owner required' using errcode='42501';
    end if;
    if requested_action not in ('SUSPEND','ARCHIVE','RESTORE','REACTIVATE')
        or length(normalized_reason) not between 10 and 1000 or command_id is null
        or (requested_action in ('SUSPEND','ARCHIVE') and reviewed_reason is not null) then
        raise exception 'Invalid lifecycle command' using errcode='23514';
    end if;
    -- Same global lock order as initial activation and capacity changes.
    select active_limit into strict capacity_limit from ops_private.character_capacity
        where singleton for update;
    select * into current_row from world_private.characters where id=target_character for update;
    if not found or not current_row.is_fixture then
        raise exception 'Fixture character not found' using errcode='23514';
    end if;
    select * into recorded from ops_private.character_lifecycle_events where request_id=command_id;
    if found then
        if recorded.character_id<>target_character or recorded.actor_user_id<>actor
            or recorded.action<>requested_action or recorded.previous_version<>expected_version
            or recorded.reason<>normalized_reason
            or recorded.reviewed_prior_reason is distinct from reviewed_reason then
            raise exception 'Lifecycle command conflict' using errcode='23514';
        end if;
        return recorded;
    end if;
    if current_row.lifecycle_version<>expected_version then
        raise exception 'Character lifecycle changed' using errcode='23514';
    end if;
    if requested_action='SUSPEND' and current_row.status='ACTIVE' then
        next_status := 'SUSPENDED';
    elsif requested_action='ARCHIVE' and current_row.status in ('ACTIVE','SUSPENDED') then
        next_status := 'ARCHIVED';
    elsif requested_action='RESTORE' and current_row.status='ARCHIVED'
        and current_row.archive_reason is not null
        and current_row.archive_reason=reviewed_reason then
        next_status := 'SUSPENDED';
    elsif requested_action='REACTIVATE' and current_row.status='SUSPENDED'
        and current_row.suspension_reason is not null
        and current_row.suspension_reason=reviewed_reason then
        next_status := 'ACTIVE';
    else
        raise exception 'Lifecycle transition not allowed' using errcode='23514';
    end if;
    if requested_action in ('RESTORE','REACTIVATE') then
        if not ops_private.current_fixture_character_source(target_character) then
            raise exception 'Current approved fixture source required' using errcode='23514';
        end if;
    end if;
    if requested_action='REACTIVATE' and
        (select count(*) from world_private.characters where status='ACTIVE')>=capacity_limit then
        raise exception 'Active character capacity reached' using errcode='23514';
    end if;
    update world_private.characters set status=next_status,
        lifecycle_version=lifecycle_version+1, updated_at=now(),
        suspension_reason=case when next_status='SUSPENDED' then normalized_reason else null end,
        archive_reason=case when next_status='ARCHIVED' then normalized_reason else null end
    where id=target_character;
    insert into ops_private.character_lifecycle_events(
        request_id,character_id,actor_user_id,action,previous_status,new_status,
        previous_version,new_version,definition_id,reason,reviewed_prior_reason)
    values(command_id,target_character,actor,requested_action,current_row.status,next_status,
        current_row.lifecycle_version,current_row.lifecycle_version+1,
        current_row.active_definition_id,normalized_reason,reviewed_reason)
    returning * into recorded;
    return recorded;
end $$;
revoke all on function ops_private.apply_fixture_character_lifecycle(uuid,text,integer,text,uuid,text)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.apply_fixture_character_lifecycle(uuid,text,integer,text,uuid,text)
    to cce_engine;

reset role;
update ops_private.schema_version set version=7 where singleton;
commit;
