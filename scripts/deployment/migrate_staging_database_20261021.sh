#!/usr/bin/env bash
# User-run VPS operation. Does not start an app, import fixtures, or modify
# production ACLs/data. It deliberately refuses an already-migrated database;
# after a partial failure, inspect the retained clone/dump before resuming.
set -euo pipefail
umask 077

readonly stage_db='hoviat_sns_stage_20261021'
readonly stage_role='hoviat_sns_stage'
readonly pg_local=(--host=/var/run/postgresql --port=5432 --username=postgres)
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repo_root="$(cd -- "${script_dir}/../.." && pwd)"
readonly audit_file="${script_dir}/audit_staging_role_20261021.sql"
readonly migrations=(
    '20260917_12_add_services_domain.sql'
    '20260917_13_seed_service_categories.sql'
    '20260917_14_add_service_row_invariants.sql'
    '20260917_15_service_state_and_tristate_relevance.sql'
    '20260917_16_service_country_code_and_state_vocabulary.sql'
    '20261016_17_add_service_bookmarks.sql'
    '20261018_18_add_service_cover_image.sql'
    '20261018_19_category_root_memberships.sql'
    '20261018_20_add_owner_profile_consent.sql'
    '20261020_21_canonical_cities_and_leaf_categories.sql'
    '20261020_22_preserve_sns_privacy_defaults.sql'
)

if [[ "$(hostname)" != 'srv5089629844' ]]; then
    echo 'STOP: intended only for VPS srv5089629844.' >&2
    exit 1
fi
if [[ ! -f "$audit_file" || ! -r "$audit_file" ]]; then
    echo 'STOP: the production privilege audit file is missing or unreadable.' >&2
    exit 1
fi
for migration in "${migrations[@]}"; do
    if [[ ! -f "${repo_root}/scripts/database/${migration}" || ! -r "${repo_root}/scripts/database/${migration}" ]]; then
        echo "STOP: migration missing or unreadable: ${migration}" >&2
        exit 1
    fi
done
sudo -v

# Each invocation logs in as postgres on the fixed Unix socket, then assumes
# ONLY the staging role before executing SQL. No password or app env is read.
stage_psql() {
    sudo -u postgres env PGOPTIONS="-c role=${stage_role} -c lock_timeout=10s -c statement_timeout=120s" \
        psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname="$stage_db" "$@"
}

echo '1/4: Auditing staging-role privileges on production (READ ONLY).'
sudo -u postgres env PGOPTIONS='-c default_transaction_read_only=on' \
    psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname=hoviat < "$audit_file"

echo '2/4: Checking the fresh staging clone before any cleanup or migrations.'
stage_psql <<'SQL'
BEGIN READ ONLY;
DO $guard$
DECLARE actual_owner text; table_count bigint;
BEGIN
    IF current_database() <> 'hoviat_sns_stage_20261021'
       OR session_user <> 'postgres' OR current_user <> 'hoviat_sns_stage'
       OR inet_server_addr() IS NOT NULL OR current_setting('port') <> '5432'
       OR current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION 'STOP: staging connection identity does not match';
    END IF;
    SELECT pg_get_userbyid(datdba) INTO actual_owner FROM pg_database WHERE datname=current_database();
    IF actual_owner <> 'hoviat_sns_stage' THEN
        RAISE EXCEPTION 'STOP: staging database owner does not match';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_database d, LATERAL aclexplode(coalesce(d.datacl, acldefault('d',d.datdba))) a
        WHERE d.datname=current_database() AND a.grantee=0
    ) THEN
        RAISE EXCEPTION 'STOP: staging database still grants privileges to PUBLIC';
    END IF;
    SELECT count(*) INTO table_count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind IN ('r','p');
    IF table_count <> 13 OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p') AND pg_get_userbyid(c.relowner) <> 'hoviat_sns_stage'
    ) THEN
        RAISE EXCEPTION 'STOP: expected the fresh 13-table staging clone owned by its role';
    END IF;
    IF to_regclass('public.users_eurobot') IS NULL OR to_regclass('public.user_privacy_settings') IS NULL
       OR to_regclass('public.sns_login_tokens') IS NULL OR to_regclass('public.job_queue') IS NULL
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
                      WHERE table_schema='public' AND table_name='user_privacy_settings' AND column_name='occupation_visibility') THEN
        RAISE EXCEPTION 'STOP: required baseline SNS schema is missing';
    END IF;
    IF EXISTS (
        SELECT 1 FROM unnest(ARRAY['services','categories','service_categories','service_contacts',
                                   'country_states','service_bookmarks','category_parents','cities','service_location_legacy']) object_name
        WHERE to_regclass('public.' || object_name) IS NOT NULL
    ) OR EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
        WHERE n.nspname='public' AND t.typname IN ('service_status','service_contact_type')
    ) THEN
        RAISE EXCEPTION 'STOP: business schema already exists or migration partially applied; do not blindly rerun';
    END IF;
    RAISE NOTICE 'PASS: baseline staging identity, owner, ACL and schema checks';
END;
$guard$;
SELECT count(*) AS copied_users FROM public.users_eurobot;
SELECT count(*) AS copied_privacy_rows FROM public.user_privacy_settings;
SELECT status,count(*) AS jobs_before_cleanup FROM public.job_queue GROUP BY status ORDER BY status;
COMMIT;
SQL

echo '3/4: Clearing only cloned staging login codes and active queue jobs.'
stage_psql <<'SQL'
BEGIN;
DO $guard$
BEGIN
    IF current_database() <> 'hoviat_sns_stage_20261021' OR current_user <> 'hoviat_sns_stage'
       OR session_user <> 'postgres' OR inet_server_addr() IS NOT NULL
       OR current_setting('port') <> '5432'
       OR (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) <> 'hoviat_sns_stage' THEN
        RAISE EXCEPTION 'STOP: cleanup is restricted to the staging clone';
    END IF;
END;
$guard$;
LOCK TABLE public.sns_login_tokens,public.job_queue IN ACCESS EXCLUSIVE MODE;
WITH removed AS (DELETE FROM public.sns_login_tokens RETURNING 1)
SELECT count(*) AS removed_cloned_login_codes FROM removed;
WITH removed AS (DELETE FROM public.job_queue WHERE status IN ('pending','processing') RETURNING 1)
SELECT count(*) AS removed_active_jobs FROM removed;
COMMIT;
SQL

echo '4/4: Applying migrations 12-22 to staging in order.'
# SQL files own their BEGIN/COMMIT. Do not wrap them in --single-transaction:
# nesting their transactions would not create one atomic all-files operation.
for migration in "${migrations[@]}"; do
    echo "Applying ${migration}"
    # The invoking user opens the source file, so postgres does not need access
    # to the upload directory or the user's private home directory.
    stage_psql < "${repo_root}/scripts/database/${migration}"
done

stage_psql <<'SQL'
BEGIN READ ONLY;
SELECT current_database() AS database,current_user AS migration_role;
SELECT count(*) AS users_after_migrations FROM public.users_eurobot;
SELECT count(*) AS privacy_rows_after_migrations FROM public.user_privacy_settings;
SELECT count(*) AS services_after_migrations FROM public.services;
SELECT count(*) AS categories_after_migrations FROM public.categories;
SELECT count(*) AS cities_after_migrations FROM public.cities;
SELECT status,count(*) AS retained_jobs FROM public.job_queue GROUP BY status ORDER BY status;
COMMIT;
SQL
echo 'DONE: staging only; completed/failed jobs and all existing user/privacy rows retained.'
echo 'No app started, no taxonomy/business import run, no Telegram or storage calls.'
echo 'Keep staging DISABLE_BACKGROUND_WORKERS=true and DEV_LOGIN_ENABLED=false.'
echo 'Rerun the privilege audit if production ACLs or role memberships change.'
