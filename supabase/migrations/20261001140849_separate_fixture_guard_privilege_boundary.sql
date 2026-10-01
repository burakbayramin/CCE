begin;
set local role cce_migrator;

-- Behavior-compatible hardening: keep the existing schema v5/API contract.
-- Non-approval contributor updates must never evaluate Owner-only queries or
-- functions, regardless of SQL boolean expression evaluation order.
create or replace function ops_private.guard_fixture_approval() returns trigger
language plpgsql set search_path='' as $$
begin
    if new.status<>'APPROVED' or old.status is not distinct from new.status then
        return new;
    end if;
    if exists(select 1 from ops_private.submission_moderation m
        where m.revision_id=new.revision_id and m.is_fixture) then
        if not ops_private.fixture_approval_allowed() then
            raise exception 'Fixture moderation cannot approve a real submission'
                using errcode='23514';
        end if;
    end if;
    return new;
end;
$$;

reset role;
commit;
