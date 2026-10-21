# SNS continuation record — 2026-10-16

Read `sns-product.md` first for the product owner's agreed scope. The current
product is business discovery/bookmarks, separate personal privacy and assigned
owner business management. Continue from the implementation below; the owner
does not need to specify each technical gap.

## Implemented locally

- Public business search now uses a dedicated privacy projection. Hidden
  contacts, owner associations, provenance and moderation status are excluded.
- Public published-only detail and active category-tree endpoints exist.
- SNS mode mounts business discovery as well as account APIs.
- Private business bookmarks use a separate table and authenticated account.
- Assigned owners can edit their business bio/name/location/contact visibility
  with locking and optimistic version checks; staff fields are excluded.
- Null privacy updates are rejected before database persistence.
- Admin country fields now use the current `country_code` contract, fixing
  create/save failures. New listings default to DE without restricting the
  international model.
- The latest consumer prototype now presents business-first home/search/detail,
  private saved businesses and assigned-owner editors. Personal account/privacy
  pages remain separate and have a business-management link.
- Public personal pages and business reads avoid shared caches so withdrawn
  fields are not retained in static pages.

## Actual application locations

- Backend: `C:\Users\asus\Projects\hoviat\hovait-fastapi`.
- Admin: `C:\Users\asus\Projects\hoviat\admin-panel-front\lumina-admin`.
- Consumer: `C:\Users\asus\Projects\hoviat\sns\hoviat-nextjs-notion-09\discover-app`.

The consumer was previously outside the attached writable roots. Changes were
prepared and built in a temporary copy, then copied to the original through
approved commands with source/destination hash checks and backups. It has no
Git repository. Do not accidentally continue one of the older numbered copies
or the old Vite admin in `hoviat-panel-nextjs/hoviat-harmony`.

The primary backup is
`C:\Users\asus\AppData\Local\Temp\sns-consumer-backup-20261016-215643`.
Later small fixes have backups ending `220411` and `220914` in the same directory.

## Verified

- 162 backend unit/API regression checks passed with the new `.venv`.
- Admin TypeScript check and production build passed.
- Consumer TypeScript and final production build passed.
- Consumer dependency installation/audit reported zero known vulnerabilities.
  Next 15.5.28 follows the
  [official maintenance release advisory](https://nextjs.org/blog/nextjs-security-update-october-14-2026).
- Actual PostgreSQL journey checks passed on the guarded local database
  `127.0.0.1:5433/hoviat_service_dev`; migration 17 was applied locally.
- Actual Next-to-API HTTP checks passed for search/detail/filtering/private
  owner reads, same-origin saves, cross-origin rejection, 409 conflicts and
  bookmark reads. A live check caught and fixed Next's request-origin/host
  mismatch in the owner proxy.
- Browser checks passed for synthetic local code sign-in, saving a business,
  owner editing, stale-edit prompt/reload/success and sign-out.
- Browser privacy change made the personal profile return 404 while its business
  stayed published. The synthetic user/business/login/queue/bookmark rows were
  then removed. The local directory currently has no published listings.

Reusable checks: `tests_manual.test_business_consumer_local` (rollback-only)
and `tests_manual.test_business_frontend_local seed|check|cleanup` (temporary
committed fixtures for separately running servers; always clean up).

## Local running state and remaining release work

Local code-free user-panel login is available as of 2026-10-17. Set backend
`DEV_LOGIN_ENABLED=true` (enabled in the local `.env`) and restart the API;
the login page discovers the option automatically. It uses one dedicated
synthetic SNS identity, creates no Telegram/channel-sync work and requires
loopback access/database with workers disabled. Its default is false. See
`docs/start-local.md` for usage. No admin authentication bypass was added.

As of 2026-10-17 the servers are stopped. Start them manually using
docs/start-local.md: API 18743, admin 18744, consumer 18745.
`DISABLE_BACKGROUND_WORKERS=true`; `.env` targets the local development DB.
The new working Python environment is `.venv`; the broken old `venv` was kept.
Consumer `.env.local` points to the local API with mock mode disabled.

Production migration/deployment and real business curation/import are pending.
No production database or deployment was changed. Public owner links remain
omitted; `show_owner` must never reveal an account without applying personal
privacy as well. Posts/social feeds and self-service ownership claiming are
future work, not current release requirements.

## Consumer design refresh — 2026-10-18

Implemented directly in the active consumer at
`C:\Users\asus\Projects\hoviat\sns\hoviat-nextjs-notion-09\discover-app`.
The earlier temporary copy is not the source for this work.

- Homepage explains discovery and business introduction, with a small support
  invitation instead of another search form.
- Search has compact controls and searchable state-to-city/category dialogs,
  separate sorting and independent relevance filters with Apply/Cancel.
- Results use responsive horizontal glass rows; business details have separate
  identity, facts, about, relevance, address and actual contact sections.
- Profile has a centered avatar hero, summary tiles, aligned information and
  existing editing/privacy/photo controls. No registration-as-verification badge.
- Five independent bottom navigation destinations include My Businesses; no
  profile/business-management mode switch. Empty owner lists invite support contact.
- The original aurora/grid background is retained. Business art uses icons
  because the public DTO has no image field; no stock listing photos were invented.

Consumer TypeScript check and production build passed. No tests or development
servers were started for this refresh; browser visual/interaction review awaits
manual startup. Support has Telegram and phone rows with explicit, non-clickable
placeholders as requested. Real contacts can later be set through public
`NEXT_PUBLIC_SUPPORT_TELEGRAM_URL` and `NEXT_PUBLIC_SUPPORT_PHONE`; shared settings
and TODO comments live in consumer `lib/support-contacts.ts` (see start-local.md).

## Admin business/category refresh and covers — 2026-10-18

- Admin business list now has visible search/filter controls, status tabs,
  removable filter chips, image thumbnails, responsive records and explicit edit
  links. Load failures have retry states and overlapping requests cannot replace
  newer filter results.
- Business editor groups information/image, category/relevance, contact and
  owner/source fields into tabs with a persistent publication/save summary.
  Existing aggregate saves and concurrency protection are retained.
- Cover selection, preview, replacement and removal are staged until Save.
  A separate version-checked media request follows the aggregate write. Partial
  image failures explicitly report that other information was saved; newly
  created listings open their existing ID so retry does not create duplicates.
- Category management has a searchable expandable hierarchy, selection/details
  panel, status filters and grouped editing. Parent choices exclude descendants;
  manually entered slugs are preserved.
- Public/owner/admin DTOs expose nullable `cover_image_url`; consumer result,
  saved-business and detail views render actual covers with icon fallbacks.
- Migration 18 adds nullable `services.cover_image_path`. Applied only to the
  guarded local `127.0.0.1:5433/hoviat_service_dev` database. Other databases and
  deployments need the migration separately. See `docs/service-cover-images.md`
  for image API, validation and existing R2/public-media configuration.

Admin and consumer TypeScript checks and production builds passed; changed
Python files passed static syntax parsing. No tests, development servers, real
image uploads or deployments were run for this change. Browser/upload behavior
still needs review after manual startup. Background-worker settings are unchanged.

## SNS usability, categories and consent — 2026-10-18

- Development login accepts an existing local user ID; blank retains the
  dedicated test identity. Missing/banned targets are refused, no Telegram login
  or queue work is triggered, and switching users recreates private client state.
  Dev JWTs have an explicit marker and a separate derived signing key, and require
  local requests/database, disabled workers and the enabled setting on every use.
- Footer selection responds immediately with a sliding blue indicator. During
  route loading an accessible skeleton replaces interaction with outgoing content;
  completion/back navigation/timeouts restore the committed selection.
- Categories now have exactly two levels. Subcategories can belong to several
  roots with a primary root; search through any parent matches them once. Admin
  editing supports this structure. Public selectors open whole main-category
  rows and deduplicate shared subcategories in search results.
- Applied migrations 19/20 and the reviewed starter taxonomy only to guarded
  `127.0.0.1:5433/hoviat_service_dev`. There are 8 main groups and 32 subcategories,
  including cross-listed catering, translation and photography. Existing service
  assignments/primary flags were preserved; no personal accounts were seeded.
- Related-person display requires admin `show_owner`, the assigned person's
  `owner_show_profile` for that business, and a discoverable personal profile.
  Existing per-field privacy is respected. A separate no-store endpoint returns
  a limited projection and the dialog rechecks it on open. Reassignment resets
  consent through both repository updates and a database trigger.
- Consumer profile editing is limited to first/last name, photo, bio and four
  guided contact methods. One Private Profile policy replaces the granular UI;
  explicit privacy Save updates the limited visible fields. Ordinary edits
  preserve hidden legacy fields. Profile/business editors use bounded dialogs
  with persistent Save/Cancel. Business contacts also guide website/email entry;
  unsupported existing contact rows are preserved.
- Consumer result cards and admin business rows have broad native link targets.
  Shared admin switch positioning no longer depends on RTL flex alignment.
- Admin scrolling cards use translucent gradients and smaller shadows without
  repeated backdrop blur/moving hover transforms. Header/dialog glass remains.
  This is a source-level simplification; scrolling performance was not profiled.
- Images continue to use the existing R2 bucket and generated public URLs, not an
  application-server image folder. No storage provider changes were needed.

Both frontend TypeScript checks and production builds passed. Python source
syntax parsing passed. No test suite, servers, browser session, live upload or
deployment was run. Start/restart all three applications manually using
`docs/start-local.md`. Other databases need migrations 19/20 separately.

## Source-based directory import — 2026-10-19

Imported the supplied five HamvatanDE posts into the guarded local development
DB as 35 published source-derived entries (IDs 772–806): 10 Bremen medical,
15 Berlin fitness/association and 10 Berlin swimming entries. Existing three
listings were preserved, including the source=test entry. No production import.

Source, structured extraction, aliases/review notes and committed ID mapping:
`data/imports/hamvatan-de-20261019/`. The idempotent snapshot importer is
`scripts/database/import_hamvatan_de.py`; default previews, --apply writes only
the guarded local DB. No existing entry is overwritten on a rerun. Added only
five category rows needed by the real material; no application schema changes.

All entries have source attribution and dated, unverified-information copy.
The suspicious dentist website and conflicting AVIVA map were withheld; original
links remain in the raw evidence. No images/coordinates/owners were invented.
Distinct practitioners and programmes sharing contacts remain separate. No
web verification, test suite, workers, servers or deployments were run.

## Profile data and directory UX corrections — 2026-10-20

- Corrected the import to represent provider profiles: removed public source
  attribution/disclaimers and 70 source/article/map-search contact rows. Original
  material remains internal. There are now 34 published imported profiles; the
  aggregate swimming-teacher listing is draft, with its two names retained as
  separate pending candidates without invented affiliation/contact details.
- Applied migration 21 only to local `127.0.0.1:5433/hoviat_service_dev`.
  `cities` now references the existing 16-state `country_states` catalogue;
  70 initial cities are defined. Services have `city_id`/`state_id` foreign keys.
  API text fields remain compatible canonical projections, protected by a DB
  trigger. `berlin`/`Berlin` resolve to Berlin and `مونیخ` to München. The literal
  test city is not a real catalogue entry; original text is retained internally
  in `service_location_legacy`. Admins can add missing cities centrally.
- `GET /api/services/services/location-catalogue/` supplies all active states
  and cities for editors; the existing locations endpoint remains published
  discovery facets. Admin city creation is permission-gated and audited at
  `POST /api/admin/service-management/locations/cities` (admin API base applies).
- First-layer categories are groups only. Admin selection, shared domain writes
  and deferred DB constraints enforce second-layer assignments. Legacy group
  assignments are migrated to their own matching child, or an explicit general
  child where no suitable assigned child exists, without guessing service type.
  Admin category management starts with collapsed groups.
- Consumer selectors are quieter with clearer steps. Profile/business contact
  editors show added contacts only; Instagram, X/Twitter, Bluesky and Discord
  are supported. LinkedIn business company pages are editable too. My Businesses
  has image-led rows; related people have an inline privacy-filtered preview;
  relevance values use compact symbols and text input focus uses soft shadows.
- Changes were reviewed at source level across agents. No tests, builds,
  browsers, application servers, workers or deployments were run in this pass.
  Start/restart the API and both frontends manually using `docs/start-local.md`.
  Other databases need migration 21 before using the updated backend.

## Search return navigation and related-person name — 2026-10-20

- Consumer discovery and the public API default to 10 results per page; admin
  pagination is unchanged.
- Related-person responses now include privacy-filtered nickname/username.
  Preview and modal use first/last name, then nickname, then username. The role
  remains the section heading. Newly supported social platforms also pass the
  related-person contact projection.
- Search result links carry their current search URL into the detail page.
  Back to Search validates the local return route, preserves filters/sort/page,
  and links to the clicked result's anchor. Direct detail visits fall back to
  unfiltered discovery; no persistent browser storage is needed.
- No tests, builds, servers, workers or deployments run in this pass.

## Simple chooser flow, public name and search relevance — 2026-10-20

- Search city/category dialogs drill from a group into its children and show
  one prominent Back button at the second level. Breadcrumbs and extra hierarchy
  navigation were removed. Bookmarks introductory text has bottom spacing.
- `nickname` is the existing shared public-name field, labelled `نام شما` in
  the consumer and `نام عمومی` in admin. Consumer editing now saves that field;
  display helpers, profiles and related-person previews prefer it consistently.
  Legacy first/last names remain intact for the existing bot/admin flows.
- No new name column or migration. SNS Telegram login and Eurobot nickname
  writes seed only an empty public name using atomic SQL CASE expressions;
  explicit account/admin edits replace it. Hilfen first/last names are not
  silently promoted to the public field. Existing privacy settings still apply.
  Changing a public name uses the existing channel-sync queue policy.
- Public search with text and no explicit sort now orders by matching name
  words, then category/profession words, then description/location words, with
  a unique ID tie-breaker. Browsing without text remains newest first. Explicit
  sort choices are preserved in search, pagination and back-navigation URLs.
- All ordering happens before PostgreSQL OFFSET/LIMIT. Total is a separate SQL
  count of the same match conditions; only the requested page is serialized.
  No extra search engine or schema migration was introduced.
- Changes received source review across agents. No tests, builds, application
  servers, workers, external calls or deployments were run in this pass.

## Authentication and privacy hardening prepared — 2026-10-20

- Removed migration 11's blanket privacy reset; added defaults-only migration
  22 and aligned ORM defaults. Existing preferences and timestamps are preserved.
  This does not recover preferences overwritten by an earlier migration run.
- Default JWT expiry now honors `ACCESS_TOKEN_EXPIRE_MINUTES`; explicit-duration
  callers are unchanged. Consumer cookie lifetime follows JWT `exp`, including
  older short-lived tokens, and expired cookies no longer imply a live session.
- Login Worker source authenticates Telegram's secret header before parsing or
  outbound calls and binds code delivery to the matching private-chat user.
  Credentials remain blank; deployment requires a matching Telegram webhook
  registration. Worker/backend shared-secret names remain compatible.
- `docs/auth-hardening-rollout.md` lists the exact narrow rollout, target
  checkout/service snapshots, database prerequisites, verification limits and
  historical privacy recovery constraints. Live rollout authorization requested.
- Changes received source review. No tests, builds, server starts/restarts,
  database migrations, external writes, Telegram calls or deployments ran while
  preparing these fixes. The live systems remain as inspected previously.


## Isolated staging preparation — 2026-10-21

- User ran the protected snapshot/clone script on srv5089629844: staging database hoviat_sns_stage_20261021 is owned by independent role hoviat_sns_stage; 13,468 users and privacy rows, 13 public tables. Retained queue history: 3,302 completed and 3 failed jobs. No application connected or migrations applied at that checkpoint.
- Prepared a read-only production privilege audit and guarded clone-only cleanup/migration runner for migrations 12–22. These scripts have not been run by the assistant; their VPS output is pending.
- Added independent Telegram and R2 write switches, default enabled for existing deployments. New staging configuration disables both, background workers and dev login, and generates fresh secrets without copying existing env files. Image uploads/removals remain unavailable until storage is isolated.
- Prepared an exclusive staging environment bootstrap for release /home/bardia/apps/sns-staging/releases/20261021-01. It checks the migrated staging database with a read-only connection and creates protected env files; it has not been executed.
- Fixed the documented relevance-sort fallback and updated stale unit fixtures for current public categories, owner consent and authorized local dev impersonation. Full offline backend suite: 193 tests passed, including 9 staging outbound-isolation tests. Tests used mocks/in-memory SQLite; no PostgreSQL or external API calls. Linux dependency installation, frontend builds and live staging checks remain pending.


## GitHub staging workflow restored — 2026-10-21

- User chose GitHub source deployment instead of the source archive. Existing VPS database clone is retained; no archive upload, migrations or app startup commands were run by the user at this checkpoint.
- Backend current features were committed on codex/sns-staging-20261021 and reconciled with remote business-discovery commit c2b27b8. Current double-services routes, public DTOs, covers and related-person consent remain; flat compatibility routes share the same handlers. Active-only category filtering/text matching from the remote change is retained for public reads, without restricting admin search.
- Admin uses hoviat2025/admin-panel-frontend (e3bcb4e). Consumer reuses bardia-corp/hoviat-sns-nextjs history (d163713), with tracked working copy C:/Users/asus/Projects/hoviat/sns/hoviat-sns-nextjs. Original local consumer folder remains untouched. All use feature branch codex/sns-staging-20261021; no default-branch merge is part of staging preparation.
- Git/Docker exclusions retain secrets, private import provenance, dumps, dependencies and archive artifacts locally. No virtual environment was created, repaired, moved or replaced.
- Existing offline backend suite after runtime merge: 193 tests passed. Database-backed manual scripts were not run; legacy fixtures are not established as compatible with canonical locations/leaf-only categories. Linux dependency installation, frontend builds, cloned-database migrations and live staging checks remain pending.
