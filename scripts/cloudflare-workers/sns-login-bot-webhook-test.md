this is not a production worker, it is the test webhook for the SNS login bot.

it is connected to our vps (staging API origin).

its job: this is the "login with code" flow for the SNS website.

- user starts the bot in Telegram, the bot greets them in Farsi and shows an
  inline button ("ورود به سایت").
- when the button is pressed, the worker calls
  POST /api/sns/auth/bot/request-login on the backend, authenticated with the
  shared API_SECRET as Bearer (backend holds it as LOGIN_BOT_API_SECRET).
- the backend upserts the user, mints a 32-char single-use login token
  (5 minute TTL) and returns it.
- the worker sends the token to the user in Farsi with usage instructions.
- the user pastes the token into the website; the website calls
  POST /api/sns/auth/exchange-token and receives the normal SNS JWT.

setup notes:

- all configuration lives as constants at the top of the .js file:
  BOT_TOKEN (the login bot's token from BotFather, used only for talking to
  Telegram), API_ORIGIN (staging API base URL, no trailing slash), and
  API_SECRET (a random string we generate; the backend holds the same value
  as LOGIN_BOT_API_SECRET and uses it to authenticate this worker).
- edit those constants in the Cloudflare editor and save - no dashboard
  variables needed.
- point the Telegram webhook at this worker with setWebhook.
- the database table sns_login_tokens must exist first (migration
  scripts/database/20260825_10_add_sns_login_tokens.sql).

related backend files:
- app/modules/sns/auth/services/bot_login.py
- app/modules/sns/auth/router.py
