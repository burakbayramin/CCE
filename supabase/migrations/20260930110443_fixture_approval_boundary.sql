begin;
set local role cce_migrator;

-- Production defaults to rejecting synthetic moderation evidence. Only the
-- loopback-only test provisioner (connecting as postgres) enables this flag.
create table ops_private.fixture_approval_policy (
    singleton boolean primary key default true check (singleton),
    enabled boolean not null default false
);
insert into ops_private.fixture_approval_policy(singleton, enabled) values (true, false);
alter table ops_private.fixture_approval_policy enable row level security;
alter table ops_private.fixture_approval_policy force row level security;
create policy migrator_fixture_policy on ops_private.fixture_approval_policy
    to cce_migrator using (true) with check (true);

create function ops_private.fixture_approval_allowed() returns boolean
language sql stable security definer set search_path='' as $$
    select coalesce((select enabled from ops_private.fixture_approval_policy
        where singleton), false)
$$;
revoke all on function ops_private.fixture_approval_allowed() from public;
grant execute on function ops_private.fixture_approval_allowed() to cce_engine;

create function ops_private.guard_fixture_approval() returns trigger
language plpgsql set search_path='' as $$
begin
    if new.status='APPROVED' and old.status is distinct from new.status
        and exists(select 1 from ops_private.submission_moderation m
            where m.revision_id=new.revision_id and m.is_fixture)
        and not ops_private.fixture_approval_allowed() then
        raise exception 'Fixture moderation cannot approve a real submission'
            using errcode='23514';
    end if;
    return new;
end;
$$;
create trigger block_fixture_approval before update on public.character_submissions
    for each row execute function ops_private.guard_fixture_approval();

create function ops_private.guard_fixture_definition() returns trigger
language plpgsql set search_path='' as $$
begin
    if exists(select 1 from ops_private.submission_moderation m
        where m.revision_id=new.revision_id and m.is_fixture)
        and not ops_private.fixture_approval_allowed() then
        raise exception 'Fixture moderation cannot create a real definition'
            using errcode='23514';
    end if;
    return new;
end;
$$;
create trigger block_fixture_definition before insert on world_private.character_definitions
    for each row execute function ops_private.guard_fixture_definition();

reset role;
commit;
