# Finish the isolated staging Telegram setup

This is a one-time operator-run preparation, explicitly authorized to reset copied
Telegram message references and pending work in the staging clone. It does not
change production data, services, or bot webhooks. Do not repeat a completed reset.

Before running, deploy both updated test Cloudflare Workers. Keep their passwords:

- Login Worker: `scripts/cloudflare-workers/sns-login-bot-staging.js`.
- Sender Worker: `scripts/cloudflare-workers/new-test-sender-bot.js`.
- Each Worker's `API_SECRET` must match its already configured staging backend
  secret (`LOGIN_BOT_API_SECRET` or `SENDER_WEBHOOK_API_SECRET`, respectively).
- Each Worker's `WEBHOOK_SECRET` will be entered privately into this setup script.
- Keep the sender Worker's existing `forward_from_chat` condition, as requested.
  Set `DEBUG_MATCHING=true` in Cloudflare for initial end-to-end diagnostics.

The test sender bot must be administrator in all three test channels and their
respective linked discussion groups. The script verifies these exact pairs:

| Channel | Channel ID | Discussion group ID |
| --- | --- | --- |
| Main | -1003941932759 | -1003741849641 |
| Public | -1003997195070 | -1003915100291 |
| Hilfen | -1003872442653 | -1003946251854 |

Run `prepare_staging_telegram_20261027.py` with `sudo .venv/bin/python`, from the
approved backend release on `srv5089629844`. It uses configured test bot tokens,
prompting privately only if tokens are missing/placeholders. It verifies bot
identities and refuses to redirect a production bot's webhook. It asks for both
Worker URLs (the login URL has a default) and their matching webhook passwords.

Once preflight succeeds, it stops only the new staging API and web services,
takes a private staging database snapshot, runs the guarded reset SQL, updates
only staging configuration and the consumer bot username, rebuilds the frontend,
registers the test webhooks, and starts staging with queue workers enabled. It
restores the real Telegram API base URL, replacing the disabled placeholder.

The reset removes the six user Telegram message IDs, `channel_updated_at`,
`telegram_messages` mappings, and pending/processing jobs. Profiles, businesses,
privacy, and completed/failed job history remain. Normal timestamp triggers run.
Existing R2 settings are retained; the bucket is still shared as authorized.

Full Telegram mode explicitly disables dev login because the existing dev-token
policy requires background workers to be disabled. Test using normal Telegram
bot login. Exchanging a code for a session queues a channel synchronization job;
requesting a code alone and dev login do not enqueue it. Queue processing remains
rate limited and channel confirmation can take time.

The sender's legacy forwarding check remains a known item to observe in the
final test. If Telegram omits `forward_from_chat`, it will skip the main callback
and job confirmations may time out. This is deliberately not changed silently.

If preflight fails, no staging configuration or database is changed. If a later
step fails, the script requests both staging services stay stopped and reports
the phase/private backup location. Keep the snapshot and inspect the partial
state before retrying. Production is unaffected.
