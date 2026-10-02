begin;
create extension if not exists pgtap with schema extensions;
select plan(8);

select has_table('ops_private','character_definition_events',
    'ordinary definition adoption has a separate audit table');
select ok((select relrowsecurity and relforcerowsecurity from pg_class
    where oid='ops_private.character_definition_events'::regclass),
    'definition adoption audit has forced RLS');
select ok(not has_table_privilege('cce_api','ops_private.character_definition_events','SELECT'),
    'contributor role cannot read adoption audit');
select ok(not has_table_privilege('cce_engine','world_private.characters','UPDATE'),
    'Owner command role cannot bypass atomic adoption command');
select ok(has_function_privilege('cce_engine',
    'ops_private.adopt_fixture_character_definition(uuid,uuid,integer,text,uuid)','EXECUTE'),
    'Owner command can execute guarded adoption');
select ok(not has_function_privilege('cce_api',
    'ops_private.adopt_fixture_character_definition(uuid,uuid,integer,text,uuid)','EXECUTE'),
    'contributor cannot adopt a definition');
select ok(not has_function_privilege('authenticated',
    'ops_private.fixture_revision_allowed(uuid,jsonb)','EXECUTE'),
    'authenticated PostgREST role cannot probe private fixture state');
select is((select count(*)::integer from pg_policies
    where schemaname='public' and tablename='submission_feedback'
        and policyname='activation_source_read'),0,
    'duplicate permissive feedback policy removed');

select * from finish();
rollback;
