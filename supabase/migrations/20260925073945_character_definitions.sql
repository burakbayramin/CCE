begin;
set local role cce_migrator;
alter table public.submission_feedback add unique(id, submission_id, revision_id);
create table world_private.character_definitions (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null,
    revision_id uuid not null unique,
    approval_id uuid not null,
    definition_version integer not null check (definition_version > 0),
    compiler_version text not null check (compiler_version='definition-v1'),
    artifact jsonb not null check (jsonb_typeof(artifact)='object'),
    artifact_sha256 text not null check (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    created_by uuid not null references public.profiles(user_id),
    created_at timestamptz not null default now(),
    foreign key(revision_id,submission_id) references public.submission_revisions(id,submission_id),
    foreign key(approval_id,submission_id,revision_id) references public.submission_feedback(id,submission_id,revision_id)
);
create index definitions_submission_idx on world_private.character_definitions(submission_id);
create index definitions_approval_idx on world_private.character_definitions(approval_id,submission_id,revision_id);
create index definitions_creator_idx on world_private.character_definitions(created_by);
alter table world_private.character_definitions enable row level security;
alter table world_private.character_definitions force row level security;
grant select,insert on world_private.character_definitions to cce_engine;
create policy owner_definition_read on world_private.character_definitions for select to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));
create policy owner_definition_insert on world_private.character_definitions for insert to cce_engine
    with check (created_by=nullif((select current_setting('cce.actor_id',true)),'')::uuid
        and exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));

create function ops_private.guard_character_definition() returns trigger
language plpgsql set search_path='' as $$
declare
    source_row record;
begin
    select r.definition,r.avatar_id,r.revision_number,f.actor_user_id,f.created_at,
        m.provider,m.policy_version,m.result,m.is_fixture,a.sha256
    into source_row
    from public.character_submissions s
    join public.submission_revisions r on r.id=s.revision_id and r.submission_id=s.id
    join public.submission_feedback f on f.id=new.approval_id and f.submission_id=s.id
        and f.revision_id=r.id and f.decision='APPROVED' and f.resulting_version=s.version
    join ops_private.submission_moderation m on m.revision_id=r.id
    left join public.avatar_assets a on a.id=r.avatar_id and a.status='READY'
    where s.id=new.submission_id and s.status='APPROVED' and r.id=new.revision_id
        and (m.result='PASS' or (m.result='REVIEW' and s.review_accepted));
    if not found then
        raise exception 'Definition requires current approved revision' using errcode='23514';
    end if;
    if new.artifact->>'schema_version' is distinct from '1'
        or new.artifact->>'compiler_version' is distinct from new.compiler_version
        or new.artifact->'proposal' is distinct from source_row.definition
        or new.definition_version<>source_row.revision_number
        or new.artifact->'source' is distinct from jsonb_build_object(
            'submission_id',new.submission_id,'revision_id',new.revision_id,
            'revision_number',source_row.revision_number,'approval_id',new.approval_id,
            'approved_by',source_row.actor_user_id,
            'approved_at',new.artifact->'source'->>'approved_at',
            'moderation_policy_version',source_row.policy_version,
            'moderation_provider',source_row.provider,'moderation_result',source_row.result,
            'is_fixture',source_row.is_fixture,'avatar_id',source_row.avatar_id,
            'avatar_sha256',source_row.sha256)
        or (new.artifact->'source'->>'approved_at')::timestamptz is distinct from source_row.created_at
        or (source_row.avatar_id is not null and source_row.sha256 is null) then
        raise exception 'Definition source mismatch' using errcode='23514';
    end if;
    return new;
end;
$$;
create trigger guard_character_definition before insert on world_private.character_definitions
    for each row execute function ops_private.guard_character_definition();
reset role;
commit;
