# Production rollout — prepared plan, 2026-10-29

**Status: preparation only.** No production migration, webhook change, environment
edit, deployment or restart is authorized by this document itself. The user will
run the reviewed VPS commands. Finish the clone rehearsal and configuration checks
before preparing the final cutover block.

### Confirmed rehearsal checkpoint

The user ran the rehearsal on the VPS successfully. Migrations 12–23 committed
on `hoviat_prod_rehearsal_20261029` in 809 ms combined (individual timings include
the psql process overhead). This does not measure live lock contention.
All 13,757 user rows and 13,757 privacy rows were preserved field-for-field;
copied login-token, queue-job and Telegram-mapping counts were unchanged.
The new directory has zero businesses, 18 seeded categories, 16 states and 70
cities. This is schema/reference-data setup, not a staging-data transfer.

Protected snapshot:
`/var/lib/postgresql/hoviat-prod-rehearsal-20261029/production.dump`.
Production services, configuration, data and webhooks were not changed.

## What stays live during preparation

- VPS: `185.202.113.95`, hostname `srv5089629844`.
- API: `/home/bardia/apps/api/backend`, `hoviat-api.service`, loopback `8000`;
  inspected source `c8b2372`, existing `.env` remains the source of production
  credentials. Preserve the API host's separate `/kariz/` upstream on `8888`.
- User panel: `/home/bardia/apps/discover`, `hoviat-discover.service`, loopback
  `3000`; inspected source `26328cb`, existing `.env.local` uses the production
  `/api/sns` URL, real login bot and mock mode off.
- Admin: `/home/bardia/apps/admin-panel`, nginx static
  root `/var/www/admin-panel`; its existing `VITE_API_URL` points to the absolute
  production API `/api` URL. Keep that URL for this rollout.
- Existing production database `hoviat` and role `hoviat`; PostgreSQL 18.4.
  Current snapshot: Node 24.18.0, npm 11.16.0, Python 3.12, about 4.2 GiB available
  RAM and 81 GiB free disk. Recheck capacity before building; build sequentially.

The tested SNS staging release and database stay separate. **Do not copy its
business rows, job history, Telegram message mappings or environment files into
production.** Do not run staging setup/cleanup scripts against production.

## 1. Freeze the release and prove the database upgrade on a fresh clone

Record the exact backend, admin and consumer commits; never cut over from an
unrecorded moving branch. Tested application heads before production preparation
were backend `9c78f9c`, admin `304b69c`, consumer `7508b90`.

Take a protected, consistent `pg_dump` of the current production database while
the old API keeps running. Restore it to a **fresh rehearsal database owned by an
independent NOLOGIN role**, with workers and external integrations unstarted.
The clone is for compatibility checks, not a replacement production database.

Audit the actual schema first, then rehearse only missing migrations, expected to
be **12–23**. Do not replay historical migrations 01–11. Record migration timing,
locks and row effects; confirm old API queries remain compatible with the additive
schema and existing user privacy, queue jobs and Telegram mappings stay intact.
Use bounded lock waits so production migration attempts fail promptly instead of
silently waiting behind live requests. Rehearsal success is a cutover prerequisite.

## 2. Prepare independent release files and production configuration

Proposed release: `/home/bardia/apps/sns-production/releases/20261029-01`, with
separate `backend`, `consumer` and `admin` folders. Install Linux dependencies and
build both frontends there **before any live restart**. Do not copy Windows
dependencies, the old Next `.next`, or staging build products.

Prepare new private environment files next to the new release; leave the running
release's environment untouched. Inspect systemd environment-file paths and
drop-ins as well, because service-level variables can override dotenv values.
Do not print credentials into logs or chat.

The candidate-venv helper
`scripts/deployment/configure_production_release_20261029.py` prepares only NEW
files after validating current production settings against the running API.
Invoke it from the candidate backend with sudo after creating its venv and
cloning the two pinned frontend sources. It preserves live files and writes
`backend/.env`, `consumer/.env.local`, and `admin/.env.production` with private
permissions. Worker copy/paste settings are retained in
`/home/bardia/apps/sns-production/private/worker-settings-20261029.env` without
printing them. Existing outputs are deliberately not overwritten on a rerun.
The helper starts no app and changes no database, unit, webhook or Cloudflare
configuration. Build sequentially only after it succeeds.

| Component | Required production values |
| --- | --- |
| Backend | Production DB target; `APP_MODE=all`; `DEV_LOGIN_ENABLED=false`; `DISABLE_BACKGROUND_WORKERS=false`; `TELEGRAM_API_ENABLED=true`; `MEDIA_WRITES_ENABLED=true`. |
| Backend secrets | Preserve existing JWT signing key, bot/login API secrets, bot tokens and R2 credentials. Add the new `SENDER_WEBHOOK_API_SECRET`, matching the prepared production sender Worker. |
| Consumer server | Explicit production `SNS_API_BASE` ending `/api/sns`; `SERVICES_API_BASE` must target the same production API `/api/services` if explicitly set; `SNS_USE_MOCK=0`; `SNS_DEV_LOGIN_ORIGIN` unset; runtime `NODE_ENV=production`. Source fallback otherwise points to old staging. |
| Consumer public build settings | `NEXT_PUBLIC_BOT_USERNAME=hoviatloginbot`; deliberate public support contacts. Set before the production build. |
| Admin public build setting | Keep the current absolute production `VITE_API_URL` ending `/api`; otherwise source fallback points to an unrelated onrender API. No new admin proxy route is required with the current URL. |

Reuse the production R2 bucket and public media base
`https://pub-4036d35baed54ee7a9504072ea49740f.r2.dev`. Do not rotate keys as an
incidental part of deployment. A consumer `SNS_INTERNAL_KEY` is not a new required
secret; use it only with a verified matching backend implementation.

Verify these **production** Telegram targets in the new configuration:

| Purpose | Channel | Discussion group |
| --- | --- | --- |
| Main | `-1001129100618` | `-1002086581533` |
| Public | `-1003443613002` | `-1003238310244` |
| Hilfen | `-1002026011030` | `-1002156702345` |

Retain other existing production target IDs unless separately reviewed. A test
configuration's active values must never overwrite these values.

## 3. Prepare and coordinate the two affected Workers

The formatter `snowy-rain-3f69` and general API proxy do not require changes for
this rollout. Preserve their current routing.

Production sender is `@alandstudentbot`, served by
`sender-bot-webhook.safaee1361.workers.dev`. Keep its production IDs and route
suffixes. Prepare the hardened sender code with a distinct Telegram
`WEBHOOK_SECRET`, the new shared sender API secret, and the production API origin.

The safe sender order is:

1. Register the existing sender URL with Telegram's matching `secret_token`
   **while the old Worker is still running and ignores the extra header**.
2. Deploy the hardened Worker, which now validates that header and sends the
   matching Bearer API secret. The old API can receive this additional header.
3. Only after confirming sender readiness, cut over the API that requires it.

Preserve pending Telegram updates; do not use `drop_pending_updates=true` as a
deployment shortcut. Do not switch to a Worker that rejects Telegram's current
header before updating the webhook registration.

Production login is a first launch for `@hoviatloginbot`. Its current old test
Worker URL must not be overwritten: prepare a **separate production login Worker**
named `sns-login-bot-production` from
`scripts/cloudflare-workers/sns-login-bot-production.js`, and keep the working test
login Worker intact. Configure production API origin,
production bot token, matching login API secret and a separate webhook secret.
Publish and check the separate, not-yet-registered production Worker before
cutover. Have its exact webhook registration command ready as well. Register the
real production bot only after the new production login API and frontends are
ready. Harmless readiness probes must not mint codes or send messages/posts.

## 4. Prepare the frontend routing switch

Prepare nginx and systemd changes in advance; do not activate them yet. Keep
consumer `/api/*` going to **Next**, because those are its authenticated BFF
routes, not direct FastAPI routes. Retain HTTPS, original Host and forwarded HTTPS
scheme. Verify `client_max_body_size 10m` on the API and consumer hosts so 5 MB
photo uploads plus multipart overhead are accepted. Preserve existing unrelated
locations and production certificates.

New Next may run on a verified-free loopback port before the public routing switch;
old and new **web** processes can coexist. Point the admin host at a prepared
static release and switch it through a validated graceful nginx reload. Preserve
old static assets/release for old tabs and rollback. Do not replace live build
files while running `next build` in the old release.

## 5. Short, ordered live cutover

Only when steps 1–4 and the final runbook are ready:

1. Take a fresh protected production backup and save current release/unit/nginx
   references. Confirm the prepared environments contain production targets.
2. Apply the rehearsed additive migrations while the old API remains live **only
   if rehearsal confirms compatibility**, with bounded lock waits. If they cannot
   finish within the agreed window, stop the attempt and keep the old application.
3. Stop the old production API/queue process before starting its replacement.
   There must be **exactly one enabled queue process** on the production DB.
   Keep pending jobs and existing Telegram mappings; never run clone cleanup here.
4. Start the prepared new API and check loopback health, read-only Eurobot/Hilfen
   API access, business reads, and sender callback authentication. No frontend
   switch until the API is healthy.
5. Switch the prepared consumer/admin routing through a validated graceful nginx
   reload. Activate the already-prepared production login webhook, then verify one
   controlled normal login on the new website. Check public HTTPS pages and that
   dev login is unavailable. No Cloudflare code editing belongs in this window.
6. Verify one controlled business edit/photo operation and expected queue behavior;
   inspect service logs. Stop the old web process only after the new one is healthy.

Do not promise zero interruption: the single API/queue replacement has a brief
restart window. All package installation, building, configuration analysis and
Worker code preparation must already be finished before that window begins.

## Rollback boundaries and remaining facts

Keep old releases, credentials, systemd/nginx configs and Worker versions. If
cutover fails, stop the new queue process first, restore old app/config pointers,
then restart exactly one old queue process. The authenticated sender Worker can
stay in place: the old API ignores its extra Authorization header. Never restore
a headerless sender Worker while the new API still enforces authentication.
Leave rehearsed backward-compatible additive schema in
place rather than dropping tables during an incident.

**Do not restore the whole pre-cutover database over production as routine
rollback:** that would discard user writes made since the backup. Any data repair
requires an explicit reconciliation plan. Uploaded R2 objects and Telegram posts
are external effects and are not reversed by a Git checkout.

Before generating the final cutover commands, still verify current full systemd
unit/drop-in contents without exposing secret values, new release ownership and
ports, rehearsal results, exact production Worker configuration/URLs and matching
secrets, webhook readiness, and the final pinned release commits.
