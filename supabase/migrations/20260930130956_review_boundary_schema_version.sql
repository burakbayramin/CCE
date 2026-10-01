begin;

-- The API may start only after all review-boundary migrations, not merely the
-- original foundation migration. The privileged postgres migration runner
-- intentionally bypasses FORCE RLS; cce_migrator has no marker read/write policy.
do $$
begin
    if (select version from ops_private.schema_version where singleton) is distinct from 1 then
        raise exception 'Expected CCE schema version 1 before review boundary migration';
    end if;
    update ops_private.schema_version set version=2 where singleton;
end;
$$;

commit;
