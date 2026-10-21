# SNS authentication fixes: prepared rollout

Prepared locally on 2026-10-20. No remote file, database, Worker, webhook or
service has been changed by this work. Application servers remain unstarted
locally. No tests or builds were run; review was source-level only.

## Exact changes

| Component | Files | Effect |
| --- | --- | --- |
| API session expiry | `app/core/security.py` | Omitted expiry now uses `ACCESS_TOKEN_EXPIRE_MINUTES`, default 10080 minutes. Explicit expiry arguments remain authoritative, including admin login. Previously issued JWTs retain their original expiry. |
| Consumer session cookie | `lib/session.ts` in the active consumer | Cookie expiry follows JWT `exp`; expired/malformed cookies no longer count as a signed-in session. Decoding is used only for cookie lifetime; API signature verification still authorizes requests. |
| Privacy schema | `app/models/user_privacy_settings.py`, migrations 11/22 | New-row defaults agree with existing login/channel insert policy. Neither corrected migration changes existing privacy rows or `updated_at`. |
| Login Worker | `scripts/cloudflare-workers/sns-login-bot-webhook-test.js` | Validates Telegram's webhook secret before JSON parsing/outbound calls; only mints/delivers codes for the matching human's private chat. |

The active consumer is:
`C:\Users\asus\Projects\hoviat\sns\hoviat-nextjs-notion-09\discover-app`.

## Keep this rollout separate from current directory development

Read-only VPS inspection found these checkouts:

- Staging: `/home/bardia/apps/api/staging/backend`, service
  `hoviat-api-staging.service`, commit `9cb9c8d` (2026-08-27).
- Production: `/home/bardia/apps/api/backend`, service
  `hoviat-api.service`, commit `c8b2372` (2026-08-28).

The local branch is much newer and contains unrelated unfinished changes.
Do not deploy the entire working tree or run migrations 12–21 as part of this
authentication fix. Prepare a narrow patch containing only the API expiry,
privacy-model/default changes and the corrected migration files. Preserve live
configuration and take normal rollback snapshots before an approved rollout.

For an existing SNS schema, migration 22 is the defaults-only forward path. Its
prerequisite is the existing privacy table with the occupation visibility column;
it does not depend on the business-directory migrations 12–21. Current live
database defaults already match it, so it is not a restoration of previous data.

## Login Worker coordination

The checked-in Worker is a staging template, not evidence of the deployed
Worker's current code/configuration. Before changing the live bot:

1. Identify its deployed Worker URL and current backend origin. Preserve the
   intended staging/production target; switching databases is a separate choice.
2. Add `BOT_TOKEN`, `API_SECRET`, and a new distinct `WEBHOOK_SECRET` as secret
   bindings; configure `API_ORIGIN` for the intended backend.
3. Deploy the hardened source and immediately register that same URL with
   Telegram `setWebhook.secret_token` equal to `WEBHOOK_SECRET`. Keep pending
   updates. A brief rejection window occurs until both sides agree.

Missing configuration fails closed with 503; absent/wrong webhook authentication
fails with 401. Never temporarily restore the unauthenticated implementation.
Detailed setup is in `scripts/cloudflare-workers/sns-login-bot-webhook-test.md`.
This changes live bot configuration and requires explicit rollout authorization.

## Privacy recovery limit

The old migration 11 overwrote existing preferences. Current source changes
prevent another blanket reset, but cannot reconstruct previous per-user values.
Do not infer consent or bulk flip current settings. Restore only from trustworthy
backups/history with reconciliation of later edits. No recovery has been applied.

## Evidence and remaining verification

Source review covers constant-time header verification, private-chat identity
binding, defaults-only SQL, configured token expiry and consumer cookie lifetime.
No runtime test, real login, Telegram message or deployment was performed.
An approved rollout still needs verification against the actual deployed Worker
and intended website/backend pairing; local source changes alone do not protect
the live Worker.
