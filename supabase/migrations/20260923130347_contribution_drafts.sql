begin;
set local role cce_migrator;
create table public.character_submissions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(user_id),
    creation_key uuid not null,
    status text not null default 'DRAFT' check (status in ('DRAFT','SUBMITTED','WITHDRAWN')),
    definition jsonb not null check (jsonb_typeof(definition)='object'
        and definition ? 'schema_version' and definition->>'schema_version'='1'),
    version integer not null default 1 check (version > 0),
    revision_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, creation_key),
    check ((status = 'DRAFT' and revision_id is null) or (status <> 'DRAFT' and revision_id is not null))
);
create index character_submissions_owner_idx on public.character_submissions(user_id, created_at desc);
create table public.submission_revisions (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null references public.character_submissions(id),
    revision_number integer not null default 1 check (revision_number > 0),
    definition jsonb not null check (jsonb_typeof(definition)='object'
        and definition ? 'schema_version' and definition->>'schema_version'='1'),
    created_at timestamptz not null default now(),
    unique(submission_id, revision_number),
    unique(id, submission_id)
);
alter table public.character_submissions add constraint submission_revision_owner_fk
    foreign key (revision_id, id) references public.submission_revisions(id, submission_id)
    deferrable initially immediate;
create index character_submissions_revision_idx on public.character_submissions(revision_id, id);
create table ops_private.contribution_events (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null references public.character_submissions(id),
    actor_user_id uuid not null references public.profiles(user_id),
    action text not null check (action in ('CREATED','SAVE','SUBMIT','WITHDRAW')),
    resulting_version integer not null check (resulting_version > 0),
    revision_id uuid,
    schema_version integer not null default 1 check (schema_version = 1),
    recorded_at timestamptz not null default now(),
    unique(submission_id, resulting_version),
    foreign key (revision_id, submission_id) references public.submission_revisions(id, submission_id)
);
create index contribution_events_actor_idx on ops_private.contribution_events(actor_user_id);
create index contribution_events_revision_idx on ops_private.contribution_events(revision_id, submission_id);

alter table public.character_submissions enable row level security;
alter table public.character_submissions force row level security;
alter table public.submission_revisions enable row level security;
alter table public.submission_revisions force row level security;
alter table ops_private.contribution_events enable row level security;
alter table ops_private.contribution_events force row level security;

grant select, insert on public.character_submissions to cce_api;
grant update (status, definition, version, revision_id, updated_at) on public.character_submissions to cce_api;
grant select, insert on public.submission_revisions to cce_api;
grant insert on ops_private.contribution_events to cce_api;
create policy own_submission on public.character_submissions to cce_api
    using (user_id=nullif((select current_setting('cce.actor_id', true)), '')::uuid
        and exists(select 1 from ops_private.current_identity()))
    with check (user_id=nullif((select current_setting('cce.actor_id', true)), '')::uuid
        and exists(select 1 from ops_private.current_identity()));
create policy own_revision_read on public.submission_revisions for select to cce_api
    using (exists(select 1 from public.character_submissions s where s.id=submission_id));
create policy own_revision_insert on public.submission_revisions for insert to cce_api
    with check (exists(select 1 from public.character_submissions s where s.id=submission_id
        and s.status='DRAFT' and s.definition=submission_revisions.definition));
create policy own_contribution_event on ops_private.contribution_events for insert to cce_api
    with check (actor_user_id=nullif((select current_setting('cce.actor_id', true)), '')::uuid
        and exists(select 1 from public.character_submissions s where s.id=submission_id
            and s.version=resulting_version));

create function ops_private.guard_submission_transition() returns trigger
language plpgsql set search_path = '' as $$
begin
    if tg_op = 'INSERT' then
        if new.status <> 'DRAFT' or new.version <> 1 or new.revision_id is not null then
            raise exception 'New submissions must be drafts' using errcode='23514';
        end if;
        return new;
    end if;
    if new.user_id <> old.user_id or new.creation_key <> old.creation_key
        or new.created_at <> old.created_at or new.id <> old.id or new.version <> old.version+1 then
        raise exception 'Invalid submission identity or version' using errcode='23514';
    end if;
    if not ((old.status='DRAFT' and new.status in ('DRAFT','SUBMITTED'))
        or (old.status='SUBMITTED' and new.status='WITHDRAWN'
            and new.definition=old.definition and new.revision_id=old.revision_id)) then
        raise exception 'Invalid submission transition' using errcode='23514';
    end if;
    if new.status='SUBMITTED' and not exists (select 1 from public.submission_revisions r
        where r.id=new.revision_id and r.submission_id=new.id and r.definition=new.definition) then
        raise exception 'Submission must match its immutable revision' using errcode='23514';
    end if;
    new.updated_at := now();
    return new;
end;
$$;
create trigger guard_submission_transition before insert or update on public.character_submissions
    for each row execute function ops_private.guard_submission_transition();
reset role;
commit;
