# VPS inventory and isolated staging plan

Read-only inspection on 2026-10-20. Host: `185.202.113.95`
(`srv5089629844`, Ubuntu 24.04). The other IP in the terminal transcript is not
part of this plan. No remote files, services, databases or Cloudflare settings
were changed during this inspection.

## Existing deployment

| Component | Location / binding | State |
| --- | --- | --- |
| Production API | `/home/bardia/apps/api/backend`, `hoviat-api.service`, `127.0.0.1:8000` | Active, checkout `c8b2372` |
| Existing staging API | `/home/bardia/apps/api/staging/backend`, `hoviat-api-staging.service`, `127.0.0.1:8010` | Active, checkout `9cb9c8d` |
| Existing consumer | `/home/bardia/apps/discover`, `hoviat-discover.service`, `127.0.0.1:3000` | Active; installed package declares Next 15.1.6 |
| Other web source | `/home/bardia/apps/web` | Package declares Next ^15.5.4; no change proposed |
| Existing admin | `/home/bardia/apps/admin-panel`, nginx root `/var/www/admin-panel` | Vite static application |
| PostgreSQL | Cluster `18-main`, loopback port 5432 | PostgreSQL/pg_dump/psql 18.4 |
| Runtime | Node 24.18.0, npm 11.16.0, Python 3.12.3 | Installed |
| Capacity snapshot | 83 GB free disk; about 4.6 GiB available RAM | Adequate for a separate release/build, monitor builds |

Existing nginx routing:

- `185.202.113.95.nip.io` → production API port 8000; also contains a separate
  `/kariz/` upstream. Preserve the whole existing virtual host.
- `staging.185.202.113.95.nip.io` → existing staging API port 8010.
- `app.185.202.113.95.nip.io` → current consumer port 3000.
- `admin.185.202.113.95.nip.io` → existing static admin root.

## Databases and shared resources

| Target | Database | Role | Approximate size |
| --- | --- | --- | --- |
| Production | `hoviat` | `hoviat` | 33 MB |
| Existing staging | `hoviat_admin_test` | `hoviat` | 33 MB |

Both databases are on local PostgreSQL. Role `hoviat` cannot create roles or
databases and is not a superuser. New role/database creation therefore needs a
PostgreSQL administrator, normally through `sudo -u postgres`.

The production and existing staging configurations currently share:

- The database role, despite different database names.
- R2 bucket `hoviat` and its access key.
- The SNS login bot and Worker-to-API login secret.

Their JWT signing keys differ. The existing API code predates the new
worker-disable switch; the inspected environment files do not set that switch.
Do not treat the old staging deployment as isolated from production side effects.
No credential values are recorded here.

Both inspected databases have SNS/privacy/login-token/job tables and do not
have the new service/category/location tables. A production clone therefore
needs the missing directory migrations 12–22, with schema checks between steps.
Do not replay historical migrations 01–11 indiscriminately. Current migration
22 preserves privacy rows; it cannot restore historical overwritten choices.

## Proposed new staging release

Leave all existing directories, services, databases and nginx roots untouched.
Use a new release directory and independently named resources, for example:

- Release root: `/home/bardia/apps/sns-staging/releases/20261021-01`.
- Database: `hoviat_sns_stage_20261021`; independent nonprivileged owner role
  `hoviat_sns_stage` and a fresh password.
- API: proposed loopback port 18753, new `hoviat-sns-stage-api.service`.
- Consumer: proposed loopback port 18755, new `hoviat-sns-stage-web.service`.
- Admin: its own static build directory; nginx routes must not replace the
  existing admin root. Separate preview HTTPS virtual hosts can be configured
  later without changing Cloudflare; verify certificates/routing first.

Those proposed ports were not listening at inspection time; check again before
starting anything. No service or hostname has been created.

### Data preparation

1. Create a restricted production `pg_dump` snapshot, schema and data together,
   using `--format=custom --no-owner --no-acl`. This reads production without
   changing its rows. Do not use production as a template database requiring
   active connections to be disconnected.
2. Create a new empty database/owner and restore only there. Retain the original
   dump as the immutable pre-migration snapshot. Never use destructive restore
   options against an existing database.
3. Verify database name, role and connection target before every migration.
   Review and apply missing migrations in order. Migrations 16/19/21 transform
   existing data, so record their before/after effects on the clone.
4. Do not reuse unexpired production login codes or queue work in writable
   staging. Preserve history in the original snapshot and prepare explicit
   clone-only cleanup. Keep workers disabled on every process using the clone.
5. Directory seed/import is separate: production has no business tables, so
   cloning production does not copy the 34 locally imported public businesses.
   Prepare a reviewed staging import; do not bypass local-only script guards.

### Source/build preparation

The backend/admin have uncommitted and untracked application files; active
consumer `sns/hoviat-nextjs-notion-09/discover-app` has no Git repository.
Deploying only the current Git commit would omit the working application.
Prepare reviewed source snapshots including required new files, while excluding
`.env*`, credentials, dumps, `.git`, virtualenvs, `node_modules`, `.next` and `dist`.
Build the Next.js consumer and Vite admin on Linux from their npm lockfiles;
do not copy Windows dependencies/build products.

### Required isolation before startup

- Explicit `APP_MODE=all` for admin/SNS together, with legacy `/webhook/` routes
  inaccessible from the preview proxy. Cron routes otherwise remain active.
- `DISABLE_BACKGROUND_WORKERS=true`, `DEV_LOGIN_ENABLED=false`.
- `TELEGRAM_API_ENABLED=false`, `MEDIA_WRITES_ENABLED=false` block request-time
  integration calls as well as disabled queue processing.
- Fresh stage JWT/login/cron secrets; never copy local or production `.env`
  wholesale. Backend URL must point only to the new staging database.
- No production Telegram or R2 write credentials. Worker disabling alone does
  not stop direct bot calls or image deletion. Writable media testing waits for
  a separate scoped staging bucket/key; existing images may be displayed only
  through read-only public URLs. Keep upload/delete unavailable until isolated.
- Consumer server `SNS_API_BASE` targets the private new API `/api/sns` base;
  service API preserves the current `/api/services/services/` routing shape.
  Admin build-time `VITE_API_URL` must explicitly target the preview API.
- Use HTTPS for the production-built consumer's Secure session cookie.

Cloudflare changes remain deferred. Before connecting a bot, a trusted loopback
call to the existing bot/request-login endpoint can issue a normal short-lived
code for a new dedicated staging-only account. It makes DB writes and queues a
job but no Telegram call; keep workers disabled and remove test jobs/account
before ever enabling them. Do not relax public dev-login loopback protections or
impersonate a real user copied from production.

## Next administrative prerequisite

Confirm interactive sudo/PostgreSQL administration from the user's SSH terminal
before preparing the new database/role. Automated `sudo -n nginx -T` did not
provide configuration output, so this inspection does not establish unattended
sudo privileges. No passwords should be pasted into chat.
