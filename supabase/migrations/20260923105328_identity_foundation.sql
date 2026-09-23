begin;

-- Supabase owns Auth grants. Create its FK as the migration runner, then transfer
-- the application table to its NOLOGIN owner; do not grant runtime access to Auth.
create table public.profiles (
    user_id uuid primary key references auth.users(id),
    created_at timestamptz not null default now()
);
alter table public.profiles owner to cce_migrator;
set local role cce_migrator;
create table world_private.people (
    id uuid primary key default gen_random_uuid(),
    display_name text not null check (length(btrim(display_name)) between 1 and 100),
    created_at timestamptz not null default now()
);
create table ops_private.world_owner (
    singleton boolean primary key default true check (singleton),
    user_id uuid not null unique references public.profiles(user_id),
    person_id uuid not null unique references world_private.people(id),
    created_at timestamptz not null default now()
);
create table ops_private.identity_audit (
    id uuid primary key default gen_random_uuid(),
    event_type text not null check (event_type = 'WORLD_OWNER_BOOTSTRAPPED'),
    actor_kind text not null check (actor_kind = 'operator'),
    actor_reference text not null check (length(btrim(actor_reference)) between 1 and 200),
    target_user_id uuid not null references public.profiles(user_id),
    reason text not null check (length(btrim(reason)) between 1 and 1000),
    idempotency_key text not null unique,
    schema_version integer not null default 1 check (schema_version = 1),
    recorded_at timestamptz not null default now()
);
create index identity_audit_target_idx on ops_private.identity_audit(target_user_id);

alter table public.profiles enable row level security;
alter table public.profiles force row level security;
alter table world_private.people enable row level security;
alter table world_private.people force row level security;
alter table ops_private.world_owner enable row level security;
alter table ops_private.world_owner force row level security;
alter table ops_private.identity_audit enable row level security;
alter table ops_private.identity_audit force row level security;

-- Only the trusted migration identity may provision the singleton Owner.
create policy provision_profiles on public.profiles to cce_migrator using (true) with check (true);
create policy provision_people on world_private.people to cce_migrator using (true) with check (true);
create policy provision_owner on ops_private.world_owner to cce_migrator using (true) with check (true);
create policy provision_identity_audit on ops_private.identity_audit to cce_migrator
    using (true) with check (true);

reset role;
-- These two narrow private Auth bridges are owned by the migration runner because
-- Supabase does not let postgres delegate Auth schema privileges to custom roles.
create function ops_private.current_identity()
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
$$;
revoke all on function ops_private.current_identity() from public, anon, authenticated, service_role;
grant execute on function ops_private.current_identity() to cce_api;

set local role cce_migrator;
grant select, insert on public.profiles to cce_api;
create policy own_profile on public.profiles to cce_api
    using (user_id = nullif((select current_setting('cce.actor_id', true)), '')::uuid
        and exists (select 1 from ops_private.current_identity()))
    with check (user_id = nullif((select current_setting('cce.actor_id', true)), '')::uuid
        and exists (select 1 from ops_private.current_identity()));

reset role;
create function ops_private.bootstrap_world_owner(
    target_user uuid, person_name text, operator_reference text, bootstrap_reason text
) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
    existing_user uuid;
    identity_id uuid;
begin
    perform pg_advisory_xact_lock(1667458353, 1);
    select user_id, person_id into existing_user, identity_id from ops_private.world_owner;
    if found then
        if existing_user <> target_user then
            raise exception 'World Owner already assigned' using errcode = '23505';
        end if;
        return identity_id;
    end if;
    if not exists (select 1 from auth.users where id = target_user
        and email_confirmed_at is not null and deleted_at is null
        and (banned_until is null or banned_until <= now())) then
        raise exception 'A confirmed, active Auth user is required' using errcode = '22023';
    end if;
    insert into public.profiles(user_id) values (target_user) on conflict do nothing;
    insert into world_private.people(display_name) values (person_name) returning id into identity_id;
    insert into ops_private.world_owner(user_id, person_id) values (target_user, identity_id);
    insert into ops_private.identity_audit(
        event_type, actor_kind, actor_reference, target_user_id, reason, idempotency_key
    ) values (
        'WORLD_OWNER_BOOTSTRAPPED', 'operator', operator_reference, target_user,
        bootstrap_reason, 'world-owner-bootstrap'
    );
    return identity_id;
end;
$$;
revoke all on function ops_private.bootstrap_world_owner(uuid, text, text, text)
    from public, anon, authenticated, service_role;
grant execute on function ops_private.bootstrap_world_owner(uuid, text, text, text) to postgres;

reset role;
commit;
