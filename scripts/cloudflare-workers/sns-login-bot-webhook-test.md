# SNS login bot webhook (staging template)

The Worker requests a single-use website login code for a person in a private
Telegram chat, then sends the code back to that same person. The backend calls
are `POST /api/sns/auth/bot/request-login` and, from the website,
`POST /api/sns/auth/exchange-token`.

**Local source updated only.** Checked-in credentials remain blank. This work
does not deploy a Worker, register a webhook, or establish that a live Worker is
protected. The unconfigured template returns HTTP 503.

## Configuration

Prefer adding these bindings to the **existing** Cloudflare Worker in its
Settings → Variables and Secrets. Use secret bindings for all three credentials;
`API_ORIGIN` can be a plain variable. No new account or service is required.
[Cloudflare secret bindings](https://developers.cloudflare.com/workers/configuration/secrets/)

| Name | Purpose |
| --- | --- |
| `BOT_TOKEN` | Login bot's BotFather credential, used to call Telegram. |
| `API_ORIGIN` | Backend origin without a trailing slash; defaults to staging. |
| `API_SECRET` | Matches backend `LOGIN_BOT_API_SECRET`; authenticates Worker → backend. |
| `WEBHOOK_SECRET` | Separate random credential matching `setWebhook.secret_token`; authenticates Telegram → Worker. |

The blank constants at the top of the script remain available as a legacy
inline fallback for the existing editor workflow. Bindings take precedence;
request configuration is passed explicitly without mutable global state. Keep
actual credentials out of the repository.

Use an unpredictable value such as 64 random hexadecimal characters for
`WEBHOOK_SECRET`. Telegram permits 1–256 characters from `A-Z`, `a-z`, `0-9`,
`_`, and `-`. Do not reuse the bot token or backend API secret.
[Telegram webhook parameters](https://core.telegram.org/bots/api#setwebhook)

The backend token table must exist first; its migration is
`scripts/database/20260825_10_add_sns_login_tokens.sql`.

## Coordinated rollout

These are manual instructions; **none of these deployment actions has been run**.
Prepare the Worker configuration and Telegram registration together, then make
both changes in the same maintenance window:

1. Deploy the hardened Worker to its existing HTTPS URL with the configuration
   above. Deliveries without a matching secret header now receive HTTP 401.
   Missing/invalid Worker configuration receives HTTP 503. There is no temporary
   unauthenticated mode.
2. Immediately call `setWebhook` for that same URL with the identical
   `WEBHOOK_SECRET` supplied as `secret_token`. Keep pending updates. Telegram
   retries failed deliveries subject to its retry limits, so a short transition
   outage is expected until both sides agree.
   [Telegram delivery behavior](https://core.telegram.org/bots/api#setwebhook)

For example, after securely setting the two temporary environment variables in
your PowerShell session, replace the URL placeholder and run:

```powershell
$loginWebhookBody = @{
    url = "https://YOUR-EXISTING-LOGIN-WORKER.workers.dev"
    secret_token = $env:SNS_LOGIN_WEBHOOK_SECRET
    allowed_updates = '["message","callback_query"]'
    drop_pending_updates = $false
}
if (-not $env:SNS_LOGIN_BOT_TOKEN -or -not $env:SNS_LOGIN_WEBHOOK_SECRET) {
    throw "Set the login bot token and matching webhook secret first."
}
Invoke-RestMethod -Method Post `
    -Uri ("https://api.telegram.org/bot{0}/setWebhook" -f $env:SNS_LOGIN_BOT_TOKEN) `
    -Body $loginWebhookBody
```

Future secret rotations require the same coordinated change on both sides.
Old headers stop working when the Worker secret changes. Do not revert to an
unauthenticated Worker to avoid this transition outage.

## Request boundaries

- Missing/invalid webhook configuration, blank credentials, or reused webhook
  credentials return HTTP 503. Non-POST methods return HTTP 405 once configured.
- Missing/incorrect `X-Telegram-Bot-Api-Secret-Token` returns HTTP 401 **before
  JSON parsing or any backend/Telegram call**. Cryptographic failures return 503.
- SHA-256 produces equal-length buffers, compared with Workers' native
  timing-resistant `crypto.subtle.timingSafeEqual`.
  [Cloudflare Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/#timingsafeequal)
- Authenticated malformed JSON returns HTTP 400.
- Messages/callbacks are ignored unless the chat is private and the human
  sender's positive numeric ID equals the chat ID. Callback identity comes from
  `callback_query.from`, not the bot author of the keyboard message. Group,
  channel, inline, or mismatched-user callbacks cannot mint or receive codes.
  Ignored updates receive HTTP 200 so Telegram does not retry them.
  [Telegram callback structure](https://core.telegram.org/bots/api#callbackquery)

Related backend files:

- `app/modules/sns/auth/services/bot_login.py`
- `app/modules/sns/auth/router.py`
