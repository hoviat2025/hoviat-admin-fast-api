this is not the main sender bot worker , but the test one that has the new features . 

it is connected to our vps . 

it's job is receiving updates from telegram , and calling needed endpoints when that happens . 

it is helping so that we can know the message id of telegram group message ids assoiciated with the channel messages we send . 

one of the main new features is the "hilfen" pattern added . and perhaps some changes in other parts of the code .

## Staging update — 2026-10-27

The changeable settings are grouped at the top of `new-test-sender-bot.js`.
Enter values directly in the Cloudflare editor, without committing real passwords:

- `WEBHOOK_SECRET`: password Telegram supplies as `secret_token` when registering
  this **test sender bot's** webhook. This is separate from the login bot webhook.
- `API_SECRET`: password matching staging backend `SENDER_WEBHOOK_API_SECRET`.
- `STAGING_API_ORIGIN`: the new isolated staging admin/API hostname.
- All source channel and destination group IDs: the approved test IDs.
- `DEBUG_PUBLIC_UPDATES`: opt-in full diagnostic updates, preserved from the
  earlier Worker; disabled by default.
- `DEBUG_MATCHING`: opt-in IDs/forwarding-field presence diagnostics, without a
  full Telegram update; disabled by default.

The `_test` suffixes are historical and are used by production too. Do not rename
them. The hostname selects the target deployment/database. The legacy
`forward_from_chat` check and the original catch/log/return-success behavior on
backend failures are deliberately preserved, per the user's instruction.

Before deploying the Worker, deploy its matching backend source to the isolated
staging release and run `scripts/deployment/configure_staging_sender_worker_20261027.py`
with `sudo .venv/bin/python` from the backend release directory. Enter the same
`API_SECRET` chosen in the Worker. The script stores the secret privately, backs
up the staging env and Nginx configuration, restarts only the staging API, then
adds only the three exact PUT callback routes through the preview password gate.
The backend authenticates all three callback routes using a Bearer secret. An
empty or missing `SENDER_WEBHOOK_API_SECRET` rejects callbacks; it never permits
anonymous requests. Any future production deployment of this source also needs
the production sender Worker and backend secret configured together.

After deploying the Cloudflare code, register the **test sender bot** webhook
with its Worker URL and the matching `WEBHOOK_SECRET`, with
`allowed_updates=["message"]`. Never change the login bot's webhook to this sender
Worker; they have different jobs.

No production vhost, production service, Telegram webhook, or queue-worker switch
is changed by these source edits. The sender setup script preserves existing
queue-worker settings. Enabling queue processing and handling cloned production
message references remain separate steps.
