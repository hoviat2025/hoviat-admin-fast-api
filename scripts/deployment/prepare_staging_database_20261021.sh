#!/usr/bin/env bash
# Run interactively as bardia on 185.202.113.95. Creates a NEW database only.
# The production database is read by pg_dump; no production SQL is changed.
set -euo pipefail
umask 077

readonly source_db='hoviat'
readonly stage_db='hoviat_sns_stage_20261021'
readonly stage_role='hoviat_sns_stage'
readonly backup_dir='/var/lib/postgresql/sns-stage-20261021'
readonly dump_file="${backup_dir}/hoviat-before-staging.dump"
readonly pg_local=(--host=/var/run/postgresql --port=5432)

if [[ "$(hostname)" != 'srv5089629844' ]]; then
    echo 'STOP: this script is intended only for VPS srv5089629844.' >&2
    exit 1
fi
sudo -v

existing=$(sudo -u postgres psql "${pg_local[@]}" -X -A -t -v ON_ERROR_STOP=1 -d postgres -c \
    "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname='hoviat_sns_stage_20261021') OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='hoviat_sns_stage');")
if [[ "$existing" != 'f' ]]; then
    echo 'STOP: the proposed staging database or role already exists. Nothing was reused.' >&2
    exit 1
fi
if sudo test -e "$backup_dir"; then
    echo 'STOP: the snapshot directory already exists. Inspect it before retrying.' >&2
    exit 1
fi

echo '1/5: Taking a protected, consistent snapshot of production.'
sudo mkdir -m 0700 -- "$backup_dir"
sudo chown postgres:postgres -- "$backup_dir"
sudo -u postgres sh -c 'umask 077; exec pg_dump "$@"' sh \
    "${pg_local[@]}" --format=custom --no-owner --no-acl \
    --lock-wait-timeout=10s --dbname="$source_db" --file="$dump_file"
sudo -u postgres pg_restore --list "$dump_file" >/dev/null
sudo chmod 0600 "$dump_file"

echo '2/5: Creating an independent staging login.'
echo 'Choose and retain a NEW staging database password at the next two prompts.'
echo 'The password is not printed. Do not paste it into chat.'
sudo -u postgres createuser "${pg_local[@]}" --login --no-superuser \
    --no-createdb --no-createrole --pwprompt "$stage_role"

echo '3/5: Creating a fresh database and restricting its access.'
sudo -u postgres createdb "${pg_local[@]}" --template=template0 --owner="$stage_role" "$stage_db"
sudo -u postgres psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 -d postgres \
    -c 'REVOKE ALL ON DATABASE hoviat_sns_stage_20261021 FROM PUBLIC;'

echo '4/5: Restoring into the new database, owned by its new role.'
# --no-comments avoids ownership-only annotation failures on preinstalled
# extensions. Original annotations remain intact in the retained full dump.
# All restore SQL is atomic; a failure leaves the new DB unpopulated.
sudo -u postgres pg_restore "${pg_local[@]}" --exit-on-error --single-transaction \
    --no-owner --no-acl --no-comments --role="$stage_role" --dbname="$stage_db" "$dump_file"

echo '5/5: Reporting metadata and row counts only.'
sudo -u postgres psql "${pg_local[@]}" -X -v ON_ERROR_STOP=1 -d "$stage_db" <<'SQL'
BEGIN READ ONLY;
SELECT current_database() AS database,
       pg_get_userbyid(datdba) AS owner,
       pg_size_pretty(pg_database_size(oid)) AS size
FROM pg_database WHERE datname=current_database();
SELECT count(*) AS copied_users FROM public.users_eurobot;
SELECT count(*) AS copied_privacy_rows FROM public.user_privacy_settings;
SELECT status,count(*) AS copied_jobs FROM public.job_queue GROUP BY status ORDER BY status;
SELECT pg_get_userbyid(c.relowner) AS table_owner,count(*) AS table_count
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p') GROUP BY c.relowner;
COMMIT;
SQL

echo "Snapshot retained privately at ${dump_file}"
echo "New database: ${stage_db}; role: ${stage_role}"
echo 'DONE: no application started, no migrations applied, no Telegram or storage calls.'
echo 'Do not connect an application yet. Next: audit role isolation, clear clone-only'
echo 'active login codes/jobs, then review/apply missing migrations and stage configuration.'
