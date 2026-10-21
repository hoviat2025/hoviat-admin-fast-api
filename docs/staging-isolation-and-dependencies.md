# Staging outbound isolation and dependency parity

Prepared locally on 2026-10-21. No server, dependency installation, deployment,
or external integration call was performed for this change.

## Required staging switches

Set these explicitly in the staging service's environment before starting it:

```env
DISABLE_BACKGROUND_WORKERS=true
TELEGRAM_API_ENABLED=false
MEDIA_WRITES_ENABLED=false
DEV_LOGIN_ENABLED=false
```

The two new outbound switches default to `true`, preserving existing production
behavior unless deliberately disabled. They are independent of the worker
switch; keep all three isolation settings above.

- `TELEGRAM_API_ENABLED=false` blocks both requests and file downloads through
  the shared Telegram client before creating an HTTP transport. Direct calls
  raise `TELEGRAM_API_DISABLED` with HTTP 503. Existing callers that intentionally
  catch errors may translate the response, but no outbound request is made.
- `MEDIA_WRITES_ENABLED=false` blocks every shared R2 upload/delete path before
  initializing or invoking the SDK. Explicit avatar and business-cover upload
  and removal operations also reject with `MEDIA_WRITES_DISABLED` / HTTP 503
  before changing their database image references.
- Existing public image URLs still render in browsers. These settings do not
  change media URL assembly or require copying images to the app server.
- Login-token issuance and ordinary database editing are separate operations;
  these switches do not make the database read-only. A login-code Worker is a
  separate deployed program and is not controlled by these backend flags.

Use a separate staging database, signing secret and API credentials. Keep bot
webhook/cron routes blocked at the staging reverse proxy, and do not populate
production bot or R2 write credentials just to satisfy settings validation.
Required credential fields can hold inert staging values while both outbound
switches are disabled. Public media URL settings may continue to reference
existing publicly served images; write access remains blocked.

## Python dependency audit

Read-only package metadata comparison found:

| Item | Local result |
| --- | --- |
| Actual runtime | Python 3.12.14, Windows |
| Pinned application requirements | 56 |
| Versions different from installed packages | None |
| Additional installed package | pip 25.0.1 (packaging tool, not an app dependency) |
| Existing lock/constraints file | None; `requirements.txt` already pins direct and transitive dependencies |

No new freeze/lock file was added: it would duplicate the existing pinned
requirements. The only dependency-list change marks `colorama==0.4.6` with
`sys_platform == "win32"`, retaining Windows console support without adding it
to Linux staging. No versions were upgraded or removed, and pip was not added
to application requirements.

Python 3.12 on staging matches the local minor version. This metadata comparison
does not establish that Linux wheels install successfully or that the staging
runtime works. Installation into the isolated staging virtual environment and
any runtime verification remain later steps. The existing Dockerfile still
specifies Python 3.11; do not assume it provides the same runtime parity.
