-- Read-only audit on PRODUCTION hoviat. Run as postgres over its local socket.
-- No ACL, role, schema or application row is changed. A failure stops psql when
-- invoked with -v ON_ERROR_STOP=1. Counts only: no profile data is selected.
BEGIN READ ONLY;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';

DO $audit$
DECLARE
    stage_role constant text := 'hoviat_sns_stage';
    stage_database constant text := 'hoviat_sns_stage_20261021';
    role_row pg_roles%ROWTYPE;
    membership_count bigint;
    relation_count bigint;
    sequence_count bigint;
    schema_count bigint;
    definer_count bigint;
    can_create_database_objects boolean;
    can_connect boolean;
BEGIN
    IF current_database() <> 'hoviat' OR session_user <> 'postgres'
       OR current_user <> 'postgres' OR inet_server_addr() IS NOT NULL
       OR current_setting('port') <> '5432'
       OR current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION 'STOP: expected PostgreSQL 18 production hoviat, postgres session, local socket port 5432';
    END IF;
    SELECT * INTO role_row FROM pg_roles WHERE rolname = stage_role;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'STOP: staging role does not exist';
    END IF;
    IF NOT role_row.rolcanlogin OR role_row.rolsuper OR role_row.rolcreatedb
       OR role_row.rolcreaterole OR role_row.rolreplication OR role_row.rolbypassrls THEN
        RAISE EXCEPTION 'STOP: staging role has unexpected login or privileged role attributes';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_database
        WHERE datname = stage_database AND datdba = role_row.oid
    ) THEN
        RAISE EXCEPTION 'STOP: expected staging database and owner do not match';
    END IF;

    -- Reject any granted role membership, even NOINHERIT memberships that may
    -- allow SET ROLE later. The database-owner pseudo-role has no such grant.
    SELECT count(*) INTO membership_count FROM pg_auth_members WHERE member = role_row.oid;

    -- Effective checks include PUBLIC, ownership and column-level grants.
    SELECT count(*) INTO relation_count
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND (has_table_privilege(stage_role, c.oid,
               'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
           OR has_any_column_privilege(stage_role, c.oid, 'SELECT,INSERT,UPDATE,REFERENCES'));
    SELECT count(*) INTO sequence_count
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
      AND c.relkind = 'S'
      AND has_sequence_privilege(stage_role, c.oid, 'USAGE,SELECT,UPDATE');
    SELECT count(*) INTO schema_count FROM pg_namespace n
    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
      AND has_schema_privilege(stage_role, n.oid, 'CREATE');
    SELECT count(*) INTO definer_count
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
      AND p.prosecdef AND has_function_privilege(stage_role, p.oid, 'EXECUTE');
    can_create_database_objects := has_database_privilege(stage_role, current_database(), 'CREATE');
    can_connect := has_database_privilege(stage_role, current_database(), 'CONNECT');

    RAISE NOTICE 'Production access audit: relations=%, sequences=%, schema_create=%, database_create=%, security_definer_execute=%, memberships=%, connect=%',
        relation_count, sequence_count, schema_count, can_create_database_objects,
        definer_count, membership_count, can_connect;
    IF relation_count <> 0 OR sequence_count <> 0 OR schema_count <> 0
       OR definer_count <> 0 OR membership_count <> 0 OR can_create_database_objects THEN
        RAISE EXCEPTION 'STOP: staging role has production object privileges. No ACLs were changed; review isolation before proceeding';
    END IF;
    RAISE NOTICE 'PASS: no effective production application-object privileges found. CONNECT may remain inherited from PUBLIC; this audit does not revoke it or guarantee future ACL changes';
END;
$audit$;
COMMIT;
