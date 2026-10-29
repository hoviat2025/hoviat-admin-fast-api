# Production SNS login Worker (prepared, not deployed)

Use `sns-login-bot-production.js` as a standalone Cloudflare editor script in a
**new, separate** Worker, suggested name `sns-login-bot-production`. It reuses
the tested staging implementation; only the environment settings and diagnostic
default differ. Do not replace the test Worker or change the test bot webhook.

All editable values are in `SETTINGS` at the start of the file:

| Setting | Production value |
| --- | --- |
| `BOT_TOKEN` | Existing production `SNS_LOGIN_BOT_TOKEN`, identity `@hoviatloginbot` |
| `API_SECRET` | Existing production `LOGIN_BOT_API_SECRET`; do not rotate it for this rollout |
| `WEBHOOK_SECRET` | New login-webhook secret, distinct from bot/API/sender credentials |
| `API_ORIGIN` | `https://185.202.113.95.nip.io` |
| `WEBSITE_URL` | `https://app.185.202.113.95.nip.io/login` |
| `EXPECTED_BOT_USERNAME` | `hoviatloginbot` |
| `DEBUG` | `false` |

Keep real credentials outside Git/chat. Secret bindings are supported for blank
credential settings; explicit inline values take precedence for the user's
Cloudflare editor workflow. Publishing a new Worker does not automatically
register a Telegram webhook.

## Activation order

1. Prepare the correctly configured production Worker, preserving the separate
   test Worker. Record the actual new Worker URL.
2. Verify production backend/login configuration and frontend readiness before
   exposing the production login flow. A signed harmless update containing only
   `update_id` checks webhook authentication without minting a code or sending a
   Telegram message; GET `OK` alone does not check configuration/readiness.
3. Verify the bot identity is `@hoviatloginbot`, then register **only that bot**
   with the new production Worker URL and matching `secret_token`. Preserve
   pending updates (`drop_pending_updates=false`). Restrict deliveries to
   `message` and `callback_query` for this login-only bot.
4. Confirm `getWebhookInfo` reports the new URL, then test one normal login with
   an agreed test account. This final functional test intentionally mints a code,
   sends a bot response, and can enqueue normal production channel work after
   successful website login; it is not a read-only probe.

No webhook registration has been performed by preparing these files. Existing
production bot tokens, API secrets, users, and Telegram message IDs are retained.

## Verification

`node --test tests/test_sns_login_worker_production.mjs` uses mocked upstreams:
no real Telegram/API requests or tokens. It covers webhook rejection, refusing
the test-bot identity, production API/website configuration, and private-chat
identity boundaries. The body/parser/timeout implementation matches the tested
staging source, including both `TextDecoder` options required by Cloudflare.
