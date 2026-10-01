begin;
set local role cce_migrator;

-- cce_api may insert avatar metadata, but only the API's verified Storage flow
-- may later promote a reserved PENDING asset to READY.
create or replace function ops_private.guard_avatar_status() returns trigger
language plpgsql set search_path='' as $$
begin
    if tg_op='INSERT' then
        if new.status<>'PENDING' then
            raise exception 'New avatar must be pending' using errcode='23514';
        end if;
    elsif old.status='READY' and new.status is distinct from old.status then
        raise exception 'Ready avatar status is immutable' using errcode='23514';
    end if;
    return new;
end;
$$;

drop trigger guard_avatar_status on public.avatar_assets;
create trigger guard_avatar_status before insert or update on public.avatar_assets
    for each row execute function ops_private.guard_avatar_status();

reset role;

-- This security migration must be present before the API is considered ready.
-- The privileged runner updates the FORCE-RLS marker, as in the v2 migration.
do $$
begin
    if (select version from ops_private.schema_version where singleton) is distinct from 2 then
        raise exception 'Expected CCE schema version 2 before avatar insert guard';
    end if;
    update ops_private.schema_version set version=3 where singleton;
end;
$$;

commit;
