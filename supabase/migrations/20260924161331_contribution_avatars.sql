begin;
set local role cce_migrator;
alter table public.character_submissions add unique(id, user_id);
create table public.avatar_assets (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null,
    user_id uuid not null references public.profiles(user_id),
    upload_key uuid not null,
    object_name text generated always as (user_id::text || '/' || id::text || '.png') stored unique,
    sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size integer not null check (byte_size between 1 and 524288),
    width integer not null check (width between 32 and 2048),
    height integer not null check (height between 32 and 2048),
    status text not null default 'PENDING' check (status in ('PENDING','READY')),
    created_at timestamptz not null default now(),
    unique(user_id,upload_key), unique(id,submission_id),
    foreign key(submission_id,user_id) references public.character_submissions(id,user_id)
);
create index avatar_assets_submission_idx on public.avatar_assets(submission_id,user_id);
alter table public.avatar_assets enable row level security;
alter table public.avatar_assets force row level security;
grant select,insert on public.avatar_assets to cce_api;
grant update(status) on public.avatar_assets to cce_api;
grant select on public.avatar_assets to cce_engine;
create policy own_avatar on public.avatar_assets to cce_api
    using (user_id=nullif((select current_setting('cce.actor_id',true)),'')::uuid
        and exists(select 1 from ops_private.current_identity()))
    with check (user_id=nullif((select current_setting('cce.actor_id',true)),'')::uuid
        and exists(select 1 from ops_private.current_identity()));
create policy owner_avatar on public.avatar_assets for select to cce_engine
    using (exists(select 1 from ops_private.current_identity() where actor_role='world_owner'));
alter table public.character_submissions add column avatar_id uuid;
alter table public.character_submissions add constraint submission_avatar_fk
    foreign key(avatar_id,id) references public.avatar_assets(id,submission_id) deferrable initially immediate;
create index submissions_avatar_idx on public.character_submissions(avatar_id,id);
alter table public.submission_revisions add column avatar_id uuid;
alter table public.submission_revisions add constraint revision_avatar_fk
    foreign key(avatar_id,submission_id) references public.avatar_assets(id,submission_id);
create index revisions_avatar_idx on public.submission_revisions(avatar_id,submission_id);
grant update(avatar_id) on public.character_submissions to cce_api;
alter policy own_revision_insert on public.submission_revisions with check (
    exists(select 1 from public.character_submissions s where s.id=submission_id
        and s.status='DRAFT' and s.definition=submission_revisions.definition
        and s.avatar_id is not distinct from submission_revisions.avatar_id)
);
create function ops_private.guard_submission_avatar() returns trigger
language plpgsql set search_path='' as $$
begin
    if old.status<>'DRAFT' and new.avatar_id is distinct from old.avatar_id then
        raise exception 'Submitted avatar cannot change' using errcode='23514';
    end if;
    if new.avatar_id is not null and not exists(select 1 from public.avatar_assets a
        where a.id=new.avatar_id and a.submission_id=new.id and a.status='READY') then
        raise exception 'Avatar must be verified and owned by submission' using errcode='23514';
    end if;
    if new.status='SUBMITTED' and not exists(select 1 from public.submission_revisions r
        where r.id=new.revision_id and r.avatar_id is not distinct from new.avatar_id) then
        raise exception 'Revision avatar mismatch' using errcode='23514';
    end if;
    return new;
end;
$$;
create trigger guard_submission_avatar before update on public.character_submissions
    for each row execute function ops_private.guard_submission_avatar();
reset role;

-- Storage is private; clients cannot invent paths or overwrite/delete an approved asset.
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
    values ('cce-avatars','cce-avatars',false,524288,array['image/png']);
create function ops_private.avatar_storage_access(object_path text, for_upload boolean)
returns boolean language sql stable security definer set search_path='' as $$
    select exists (
        select 1 from public.avatar_assets a
        join auth.users u on u.id=auth.uid()
        join auth.sessions s on s.user_id=u.id and s.id=(auth.jwt()->>'session_id')::uuid
        where a.object_name=object_path and u.deleted_at is null and u.email_confirmed_at is not null
        and (u.banned_until is null or u.banned_until<=now())
        and (s.not_after is null or s.not_after>now())
        and (
            (a.user_id=u.id and (not for_upload or a.status='PENDING'))
            or (not for_upload and a.status='READY' and exists(
                select 1 from ops_private.world_owner w where w.user_id=u.id))
        )
    )
$$;
revoke all on function ops_private.avatar_storage_access(text,boolean)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.avatar_storage_access(text,boolean) to authenticated;
create policy cce_avatar_upload on storage.objects for insert to authenticated
    with check (bucket_id='cce-avatars' and ops_private.avatar_storage_access(name,true));
create policy cce_avatar_read on storage.objects for select to authenticated
    using (bucket_id='cce-avatars' and ops_private.avatar_storage_access(name,false));
commit;
