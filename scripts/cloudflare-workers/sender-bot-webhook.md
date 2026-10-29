this is the main sender bot worker and is active .

it is connected directly to the VPS HTTPS API origin .

it's job is receiving updates from telegram , and calling needed endpoints when that happens .

it is helping so that we can know the message id of telegram group message ids assoiciated with the channel messages we send .

if you decide to change this file make sure to preserve comments and everything as much as possible and avoid changes when not needed .

## Prepared production update (not automatically deployed)

`sender-bot-webhook.js` is the production template. Its deployed settings are all
at the top. Both secret strings are intentionally blank in Git; fill the private
Cloudflare copy before deployment. This Worker has no BotFather token and never
sends Telegram messages: it receives updates and sends message-ID mappings to
the backend. The existing comments/scenarios and historical `_test` paths remain.

The production origin is `https://185.202.113.95.nip.io`. Main/source channel,
public channel, Hilfen channel and their discussion groups are explicitly
separate settings. They must match the production backend; none are staging IDs.
The known `forward_from_chat` criterion remains unchanged. Do not add an assumed
`forward_origin` fallback without inspecting a genuine production update first.

### Ordered rollout, before the backend cutover

1. Save the current deployed Worker version and Telegram webhook settings.
   Retain the existing webhook URL, allowed updates and pending updates.
2. Choose a private `WEBHOOK_SECRET` accepted by Telegram (`A-Z`, `a-z`, digits,
   `_`, `-`, 1–256 characters). Register it via `setWebhook` **while the old
   Worker is still deployed**: the old Worker ignores the added header. Keep
   the same webhook URL and do not set `drop_pending_updates=true`.
3. Fill this Worker's `WEBHOOK_SECRET` with that exact value. Fill `API_SECRET`
   with the production backend's planned `SENDER_WEBHOOK_API_SECRET`. Deploy the
   prepared Worker only after webhook registration succeeds. It adds a Bearer
   header that the old backend ignores, so this can precede the backend restart.
4. Verify real sender callbacks still arrive, the API returns success, and the
   bot's `getWebhookInfo` has no new delivery errors. No synthetic message sends
   are required for this configuration step.
5. At the planned backend cutover, load the matching `SENDER_WEBHOOK_API_SECRET`
   into the new backend. Preserve all production mapping rows and message IDs.

This is an ordering requirement, not a command to execute before the complete
production runbook is approved. It does not change any bot webhook by itself.

### Failure and rollback behavior

Missing settings return 503; missing/incorrect Telegram secret returns 401 before
the body is parsed or an API request is made. Bad/oversized updates return 400.
Only updates from the exact configured discussion group/channel combinations
match. PUT calls time out after eight seconds and refuse redirects, so the API
password cannot be forwarded to another host.

Backend non-2xx responses and network failures return **503**. Telegram retries
unsuccessful delivery; do not delete the webhook or clear pending updates to
"fix" a backlog. Duplicate delivery is possible after an ambiguous response,
and the existing backend mapping upserts tolerate it. A persistent 401 means
secrets disagree; a persistent 4xx mapping error needs inspection rather than
being silently acknowledged.

Rolling the backend back to its older code can retain the updated Worker:
the older backend ignores its Authorization header. Do **not** roll only the
Worker back to headerless code while the new backend is enforcing authentication.
Adding the webhook secret remains compatible with the original header-ignoring
Worker if a coordinated rollback is needed.

### Offline checks

```powershell
node --test tests/test_sender_worker.mjs
```

These checks use an isolated JavaScript VM, mocked `fetch` and local crypto.
They do not contact Cloudflare, Telegram, the VPS, a database, or R2.

References: [Workers Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/),
[Workers request redirects](https://developers.cloudflare.com/workers/runtime-apis/request/),
[Telegram webhook delivery](https://core.telegram.org/bots/api#setwebhook).
