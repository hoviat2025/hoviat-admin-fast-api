# Separate staging login bot

Worker source: `sns-login-bot-staging.js`. It is a dashboard-pasteable ES module.
All changeable settings are grouped at the top of that file. No real credentials
are stored in the repository. This is separate from the existing production bot.

## 1. Create a test bot

In Telegram, open `https://t.me/BotFather`, send `/newbot`, and create a separate
bot, for example with display name `Hoviat Staging Login`. Its unique username
must end in `bot`. Keep the resulting token privately. Do not change the webhook
of the existing `hoviatloginbot`.

## 2. Prepare the VPS route

On the approved staging VPS, from the approved backend release, run the deployment
script `scripts/deployment/expose_staging_login_worker_20261027.py` with sudo.
It permits automated access only to `/api/sns/auth/bot/request-login` on the
staging admin hostname. The backend still requires its existing Worker Bearer
secret. All other browser routes retain the preview gate. The script backs up
the staging Nginx file and tests configuration before reloading; it restores the
old file on validation/reload failure. Production vhosts are not edited.

## 3. Create a separate Cloudflare Worker

Use a separate Worker such as `hoviat-login-staging`. Paste the ES module source
into its code editor. Fill the three empty strings in the `SETTINGS` block at the
very top of the code directly in Cloudflare. The URL defaults are already correct
for staging. This is the user's preferred setup; Variables and Secrets bindings
are optional and override the matching code values if present.

| Name in `SETTINGS` | Optional binding type | Value |
| --- | --- | --- |
| `BOT_TOKEN` | Secret | New test bot's BotFather token |
| `API_SECRET` | Secret | Staging backend's `LOGIN_BOT_API_SECRET` |
| `WEBHOOK_SECRET` | Secret | A separate random URL-safe value; use the same value when registering the webhook |
| `API_ORIGIN` | Text, optional | `https://sns-admin-stage.185.202.113.95.nip.io` (already the source default) |
| `WEBSITE_URL` | Text, optional | `https://sns-stage.185.202.113.95.nip.io/login` (already the source default) |

Read the API secret privately on the VPS (do not paste the output into chat):

```bash
cd /home/bardia/apps/sns-staging/releases/20261021-01/backend
sudo .venv/bin/python -c 'from app.core.config import settings; print(settings.LOGIN_BOT_API_SECRET)'
```

Generate a separate webhook secret privately:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Keep that generated value so the webhook registration can use the exact same
one. Deploy the code and settings, then note the Worker's HTTPS workers.dev URL.

## 4. Register the test bot webhook

Set Telegram's webhook for the **new test bot only**, using the deployed Worker
URL, `secret_token` equal to `WEBHOOK_SECRET`, and `allowed_updates` equal to
`["message","callback_query"]`. Do not embed real values in tracked files.
Registration is a separate operator step after the bot and Worker URL are known.

The Worker authenticates Telegram's secret header before parsing the update. It
only issues login codes for private chats belonging to the requesting Telegram
user. It acknowledges callbacks promptly, checks upstream success responses, and
does not log credentials, tokens or raw upstream errors. Outbound failures tell
the user to retry. There is no durable update deduplication; repeated presses
may create multiple independently single-use codes.

## 5. Use the test bot from the staging website

Set the consumer's `NEXT_PUBLIC_BOT_USERNAME` to the new test bot's username
without `@`, rebuild only the staging consumer, and restart only its staging
service. The code entry and token exchange already use the staging backend.

Start the test bot, press its login button, and enter the resulting code on the
staging website. Preview access is still `preview` plus the configured preview
password. Dev login can remain available independently.

## Channel posting stays off

This login Worker does not select channels or run the backend queue. Keep
`DISABLE_BACKGROUND_WORKERS=true` and `TELEGRAM_API_ENABLED=false` while preparing
login. Test-channel configuration and cloned Telegram message references need a
separate review before enabling queue workers.
