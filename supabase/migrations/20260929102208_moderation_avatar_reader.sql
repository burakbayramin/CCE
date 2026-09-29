begin;

-- A tagged Auth identity is only a Storage reader, never an application actor.
-- Read current server-side metadata so revocation is immediate even if an old
-- access token still carries the earlier app_metadata snapshot.
create or replace function ops_private.current_identity()
returns table(actor_role text, person_id uuid)
language sql stable security definer set search_path = '' as $$
    select case when w.user_id is null then 'contributor' else 'world_owner' end, w.person_id
    from auth.users u
    join auth.sessions s on s.user_id = u.id
    left join ops_private.world_owner w on w.user_id = u.id
    where u.id = nullif(current_setting('cce.actor_id', true), '')::uuid
      and s.id = nullif(current_setting('cce.session_id', true), '')::uuid
      and u.deleted_at is null and u.email_confirmed_at is not null
      and (u.banned_until is null or u.banned_until <= now())
      and (s.not_after is null or s.not_after > now())
      and coalesce(u.raw_app_meta_data->>'cce_role', '') <> 'moderation_worker'
$$;

-- A worker-tagged account must not also inherit contributor/Owner Storage
-- access from the existing policy, even if it previously owned an avatar.
create or replace function ops_private.avatar_storage_access(object_path text, for_upload boolean)
returns boolean language sql stable security definer set search_path='' as $$
    select exists (
        select 1 from public.avatar_assets a
        join auth.users u on u.id=auth.uid()
        join auth.sessions s on s.user_id=u.id and s.id=(auth.jwt()->>'session_id')::uuid
        where a.object_name=object_path and u.deleted_at is null and u.email_confirmed_at is not null
        and (u.banned_until is null or u.banned_until<=now())
        and (s.not_after is null or s.not_after>now())
        and coalesce(u.raw_app_meta_data->>'cce_role','')<>'moderation_worker'
        and (
            (a.user_id=u.id and (not for_upload or a.status='PENDING'))
            or (not for_upload and a.status='READY' and exists(
                select 1 from ops_private.world_owner w where w.user_id=u.id))
        )
    )
$$;

create index moderation_jobs_running_avatar_idx
    on ops_private.moderation_jobs(avatar_id)
    where state='RUNNING' and avatar_id is not null;
alter table ops_private.moderation_jobs add column auth_worker_user_id uuid
    references auth.users(id) on delete set null;
create unique index moderation_jobs_one_running_per_auth_worker_idx
    on ops_private.moderation_jobs(auth_worker_user_id)
    where state='RUNNING' and auth_worker_user_id is not null;

-- One live attempt per Auth worker identity. The assignment and claim commit
-- together, so Storage never sees an unassigned live attempt from this path.
create function ops_private.claim_moderation_for_worker(target_user uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare
    payload jsonb;
begin
    perform pg_advisory_xact_lock(1667458353, 2);
    if not exists(select 1 from auth.users u where u.id=target_user
        and u.raw_app_meta_data->>'cce_role'='moderation_worker'
        and u.deleted_at is null and u.email_confirmed_at is not null
        and (u.banned_until is null or u.banned_until<=now())) then
        raise exception 'Active moderation Auth identity required' using errcode='42501';
    end if;
    if exists(select 1 from ops_private.moderation_jobs j
        where j.auth_worker_user_id=target_user and j.state='RUNNING'
            and j.lease_until>now()) then
        return null;
    end if;
    payload := ops_private.claim_moderation();
    if payload is not null then
        update ops_private.moderation_jobs set auth_worker_user_id=target_user
            where id=(payload->>'job_id')::uuid;
    end if;
    return payload;
end;
$$;
revoke all on function ops_private.claim_moderation_for_worker(uuid)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.claim_moderation_for_worker(uuid) to cce_worker_cpu;

-- The DB worker can resolve only an avatar belonging to its live attempt.
-- It releases the connection before requesting bytes from Storage.
create function ops_private.moderation_avatar_path(
    target_job uuid, target_attempt uuid, target_user uuid
)
returns text language sql stable security definer set search_path='' as $$
    select a.object_name
    from ops_private.moderation_jobs j
    join public.character_submissions s on s.id=j.submission_id
        and s.status='UNDER_REVIEW' and s.revision_id=j.revision_id
    join public.submission_revisions r on r.id=j.revision_id and r.submission_id=s.id
        and r.avatar_id=j.avatar_id
    join public.avatar_assets a on a.id=j.avatar_id and a.status='READY'
        and a.sha256=j.avatar_sha256
    where j.id=target_job and j.active_attempt_id=target_attempt
        and j.auth_worker_user_id=target_user
        and j.state='RUNNING' and j.lease_until>now()
$$;
revoke all on function ops_private.moderation_avatar_path(uuid,uuid,uuid)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.moderation_avatar_path(uuid,uuid,uuid) to cce_worker_cpu;

-- Storage is given only a yes/no answer. The Auth worker never receives table
-- privileges, and SELECT is limited to the authenticated object GET operations.
create function ops_private.moderation_avatar_storage_access(object_path text)
returns boolean language sql stable security definer set search_path='' as $$
    select exists (
        select 1
        from public.avatar_assets a
        join ops_private.moderation_jobs j on j.avatar_id=a.id
            and j.avatar_sha256=a.sha256 and j.state='RUNNING'
            and j.lease_until>now()
        join public.character_submissions c on c.id=j.submission_id
            and c.status='UNDER_REVIEW' and c.revision_id=j.revision_id
        join public.submission_revisions r on r.id=j.revision_id
            and r.submission_id=c.id and r.avatar_id=a.id
        join auth.users u on u.id=(select auth.uid())
            and u.id=j.auth_worker_user_id
        join auth.sessions s on s.user_id=u.id
            and s.id=nullif((select auth.jwt()->>'session_id'),'')::uuid
        where a.object_name=object_path and a.status='READY'
            and u.raw_app_meta_data->>'cce_role'='moderation_worker'
            and u.deleted_at is null and u.email_confirmed_at is not null
            and (u.banned_until is null or u.banned_until<=now())
            and (s.not_after is null or s.not_after>now())
    )
$$;
revoke all on function ops_private.moderation_avatar_storage_access(text)
    from public,anon,authenticated,service_role;
grant execute on function ops_private.moderation_avatar_storage_access(text) to authenticated;
create policy cce_moderation_avatar_read on storage.objects for select to authenticated
    using (bucket_id='cce-avatars'
        and storage.allow_any_operation(array[
            'object.get_authenticated', 'object.get_authenticated_info'
        ])
        and ops_private.moderation_avatar_storage_access(name));

commit;
