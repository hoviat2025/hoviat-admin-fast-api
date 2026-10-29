#!/usr/bin/env bash
# Rehearse business migrations on a NEW production snapshot, never on hoviat.
# No app, worker, webhook, Telegram or R2 setup is performed. Copied users,
# privacy choices, login tokens, queue jobs and Telegram mappings are retained.
set -euo pipefail
umask 077

readonly production_repo='/home/bardia/apps/api/backend'
readonly production_commit='c8b2372b5ccbc575b7cd2037deb1c0c60b00c8e0'
readonly rehearsal_db='hoviat_prod_rehearsal_20261029'
readonly rehearsal_role='hoviat_prod_rehearsal'
readonly snapshot_dir='/var/lib/postgresql/hoviat-prod-rehearsal-20261029'
readonly snapshot="${snapshot_dir}/production.dump"
readonly pg_local=(--host=/var/run/postgresql --port=5432 --username=postgres)
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repo_root="$(cd -- "${script_dir}/../.." && pwd)"
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
    '20261028_23_default_new_owner_profile_visibility.sql'
)

phase='preflight'
trap 'printf "STOP during %s (script line %s). Any prepared rehearsal objects and private snapshot are retained; do not rerun or delete them blindly.\n" "$phase" "$LINENO" >&2' ERR

test "$(hostname)" = 'srv5089629844'
test "$(systemctl show hoviat-api.service -p WorkingDirectory --value)" = "$production_repo"
test "$(systemctl is-active hoviat-api.service)" = 'active'
test "$(git -C "$production_repo" rev-parse HEAD)" = "$production_commit"
git -C "$production_repo" diff --quiet
git -C "$production_repo" diff --cached --quiet
git -C "$repo_root" diff --quiet -- scripts/database
git -C "$repo_root" diff --cached --quiet -- scripts/database
for migration in "${migrations[@]}"; do
    test -f "${repo_root}/scripts/database/${migration}"
    test -r "${repo_root}/scripts/database/${migration}"
done
sudo -v
if sudo test -e "$snapshot_dir"; then
    echo 'STOP: the private rehearsal snapshot directory already exists.' >&2
    exit 1
fi

# Production access is restricted to catalog inspection and a read-only dump.
sudo -u postgres env PGOPTIONS='-c default_transaction_read_only=on -c lock_timeout=2s -c statement_timeout=60s' \
    psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname=hoviat <<'SQL'
DO $guard$
BEGIN
    IF current_database() <> 'hoviat' OR current_user <> 'postgres'
       OR inet_server_addr() IS NOT NULL OR current_setting('port') <> '5432'
       OR current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION 'Expected production hoviat on the PostgreSQL 18 local socket';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname='hoviat_prod_rehearsal_20261029')
       OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='hoviat_prod_rehearsal') THEN
        RAISE EXCEPTION 'The rehearsal database or role already exists';
    END IF;
    IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p')) <> 13
       OR to_regclass('public.services') IS NOT NULL
       OR to_regclass('public.categories') IS NOT NULL THEN
        RAISE EXCEPTION 'Production no longer matches the reviewed 13-table pre-business baseline';
    END IF;
END
$guard$;
SQL

phase='consistent production snapshot'
echo '1/5: Taking a protected, consistent read-only production snapshot.'
sudo -u postgres mkdir -m 0700 "$snapshot_dir"
sudo -u postgres env PGOPTIONS='-c default_transaction_read_only=on' \
    pg_dump "${pg_local[@]}" --dbname=hoviat --format=custom --no-owner --no-acl \
    --lock-wait-timeout=2s --file="$snapshot"

phase='creating the isolated rehearsal database'
echo '2/5: Creating a new NOLOGIN owner and an independent database.'
sudo -u postgres psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname=postgres \
    -c 'CREATE ROLE hoviat_prod_rehearsal NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;'
sudo -u postgres createdb "${pg_local[@]}" --template=template0 \
    --owner="$rehearsal_role" "$rehearsal_db"
sudo -u postgres psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname=postgres \
    -c 'REVOKE ALL ON DATABASE hoviat_prod_rehearsal_20261029 FROM PUBLIC;'

# A different locale would make the rehearsal misleading. Fail before restore
# if template0 did not produce the same database locale as production.
sudo -u postgres psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname=postgres <<'SQL'
DO $guard$
BEGIN
    IF (SELECT ROW(encoding,datlocprovider,datcollate,datctype,datlocale,daticurules)
        FROM pg_database WHERE datname='hoviat') IS DISTINCT FROM
       (SELECT ROW(encoding,datlocprovider,datcollate,datctype,datlocale,daticurules)
        FROM pg_database WHERE datname='hoviat_prod_rehearsal_20261029') THEN
        RAISE EXCEPTION 'Rehearsal locale differs from production; retain the snapshot and review before continuing';
    END IF;
END
$guard$;
SQL

phase='restoring the independent rehearsal database'
echo '3/5: Restoring the snapshot into rehearsal. No application is connected.'
# Restore diagnostics remain private because a data error could include a row
# value. Do not paste restore.log into chat without reviewing/redacting it.
sudo -u postgres bash -c 'log=$1; shift; exec pg_restore "$@" 2>"$log"' \
    rehearsal-restore "${snapshot_dir}/restore.log" "${pg_local[@]}" \
    --dbname="$rehearsal_db" --role="$rehearsal_role" \
    --exit-on-error --no-owner --no-acl "$snapshot"

rehearsal_psql() {
    sudo -u postgres env PGOPTIONS="-c role=${rehearsal_role} -c lock_timeout=2s -c statement_timeout=120s" \
        psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 --dbname="$rehearsal_db" "$@"
}

phase='validating the restored rehearsal baseline'
rehearsal_psql <<'SQL'
BEGIN READ ONLY;
DO $guard$
BEGIN
    IF current_database() <> 'hoviat_prod_rehearsal_20261029'
       OR current_user <> 'hoviat_prod_rehearsal' OR session_user <> 'postgres'
       OR inet_server_addr() IS NOT NULL OR current_setting('port') <> '5432'
       OR current_setting('server_version_num')::integer / 10000 <> 18
       OR (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) <> current_user THEN
        RAISE EXCEPTION 'Rehearsal connection identity/ownership does not match';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_database d,
        LATERAL aclexplode(coalesce(d.datacl,acldefault('d',d.datdba))) a
        WHERE d.datname=current_database() AND a.grantee=0) THEN
        RAISE EXCEPTION 'The rehearsal database still grants privileges to PUBLIC';
    END IF;
    IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p')) <> 13
       OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                  WHERE n.nspname='public' AND c.relkind IN ('r','p')
                    AND pg_get_userbyid(c.relowner) <> current_user) THEN
        RAISE EXCEPTION 'Expected 13 restored public tables owned by the rehearsal role';
    END IF;
    IF to_regclass('public.users_eurobot') IS NULL
       OR to_regclass('public.user_privacy_settings') IS NULL
       OR to_regclass('public.sns_login_tokens') IS NULL
       OR to_regclass('public.job_queue') IS NULL
       OR to_regclass('public.telegram_messages') IS NULL
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
                      AND table_name='user_privacy_settings' AND column_name='occupation_visibility')
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
                      AND table_name='users_eurobot' AND column_name='occupation') THEN
        RAISE EXCEPTION 'The restored baseline lacks SNS/login/occupation prerequisites';
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(ARRAY['services','categories','service_categories','service_contacts',
        'country_states','service_bookmarks','category_parents','cities','service_location_legacy']) name
        WHERE to_regclass('public.' || name) IS NOT NULL) THEN
        RAISE EXCEPTION 'Unexpected business tables already exist in the restored baseline';
    END IF;
END
$guard$;
COMMIT;
SQL

# Ordered hashes cover every stored field (including timestamps), without
# printing personal information. They are calculated ONLY on the offline copy.
fingerprint() {
    rehearsal_psql -Atq <<'SQL'
SELECT count(*)::text || ':' || md5(coalesce(string_agg(md5(row_to_json(u)::text),'' ORDER BY user_id),''))
FROM public.users_eurobot u;
SELECT count(*)::text || ':' || md5(coalesce(string_agg(md5(row_to_json(p)::text),'' ORDER BY user_id),''))
FROM public.user_privacy_settings p;
SELECT count(*) FROM public.sns_login_tokens;
SELECT count(*) FROM public.job_queue;
SELECT count(*) FROM public.telegram_messages;
SQL
}
before="$(fingerprint)"

phase='rehearsing migrations 12 through 23'
echo '4/5: Applying ONLY migrations 12-23 to rehearsal, measuring each one.'
# Each source SQL file owns its BEGIN/COMMIT. Do not nest them in a wrapper
# transaction or use the staging runner, which clears cloned tokens/jobs.
for migration in "${migrations[@]}"; do
    printf 'Applying %s\n' "$migration"
    started_ns="$(date +%s%N)"
    rehearsal_psql < "${repo_root}/scripts/database/${migration}"
    elapsed_ms=$(( ($(date +%s%N) - started_ns) / 1000000 ))
    printf 'Completed %s in %s ms\n' "$migration" "$elapsed_ms"
done

phase='checking preservation and reporting results'
after="$(fingerprint)"
test "$before" = "$after"
echo '5/5: PASS: all user/privacy fields and copied login/job/message counts are unchanged.'
rehearsal_psql <<'SQL'
BEGIN READ ONLY;
SELECT current_database() AS database,current_user AS migration_role;
SELECT count(*) AS users FROM public.users_eurobot;
SELECT count(*) AS privacy_rows FROM public.user_privacy_settings;
SELECT count(*) AS business_rows FROM public.services;
SELECT count(*) AS categories FROM public.categories;
SELECT count(*) AS states FROM public.country_states;
SELECT count(*) AS cities FROM public.cities;
SELECT column_name,column_default FROM information_schema.columns
WHERE table_schema='public' AND table_name='services' AND column_name='owner_show_profile';
COMMIT;
SQL
printf 'Private production snapshot retained: %s\n' "$snapshot"
echo 'DONE: production data/config/services and staging were not changed.'
echo 'No app was started and no external API was called. All copied Telegram ids, tokens and jobs were retained.'
