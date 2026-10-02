# Local development safety

This note covers running the API locally against a copy of the production
database, and the one switch that makes that safe.

## The problem

On startup the application always did three things that are fine in production
but not against a local copy of the data:

1. Ran the queue startup-recovery pass (`recover_orphaned_jobs`), which rewrites
   `job_queue` rows left in `PROCESSING`.
2. Started the **Background Lane** and **VIP Lane** queue workers.
3. Started the R2 storage client.

The workers matter. A worker picks the next `PENDING` row from `job_queue` and
runs `UpdateChannelPostService.execute()`, which **publishes to the real Telegram
channels** using the bot tokens from `.env`. A local copy of the database
contains real `job_queue` rows, so a local server can post real messages.

The dangerous part is that merely *editing data* creates work:

- `UserManagementService.update_user` enqueues a medium-priority channel sync by
  default (`sync_channels=True`). Using the admin user editor locally would
  therefore enqueue a job, and the local worker would publish it.
- `POST /webhook/hoviat/v1/cron-sync` enqueues low-priority syncs for every user
  whose channel post is missing or stale. It is protected by
  `CRON_SYNC_SECRET`, but on a local machine that secret is whatever you set.

## The switch

```env
DISABLE_BACKGROUND_WORKERS=true
```

When true, the process:

- does **not** start the background or VIP queue workers, and
- does **not** run the queue startup-recovery pass.

Everything else (routers, admin API, database access) behaves normally. No
Telegram channel job can be executed by the process, so local API development
cannot publish anything.

The setting defaults to `False`, so **production behaviour is unchanged**: the
workers and recovery run exactly as before unless the variable is explicitly set.

Set it in your local `.env` only. Do not set it on the server.

## What is still not isolated

Be aware of these while developing locally:

- **R2 storage client** still starts. Any endpoint that uploads to R2 (for
  example the SNS profile-picture upload) will write to the real bucket.
- **Outbound Telegram calls from request handlers** are not blocked by this
  switch. The switch stops the queue workers, not every possible code path that
  talks to Telegram. The bot tokens in a local `.env` are real tokens, so avoid
  exercising flows that send messages (channel sync, login-code bot, Hilfen
  webhooks) unless you intend to.
- **Inbound Telegram webhooks** cannot reach a local process unless you expose
  it, so the webhook routers are inert locally.

## Running the API locally

```bash
# venv + deps
pip install -r requirements.txt

# .env must point at the local database and disable the workers
#   DATABASE_URL=postgresql+asyncpg://<user>:<password>@127.0.0.1:5432/<db>
#   DISABLE_BACKGROUND_WORKERS=true

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify at runtime that you are on the intended database before trusting anything:

```python
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as s:
        print((await s.execute(text(
            "select current_database(), inet_server_addr()::text, inet_server_port()"
        ))).first())
```

On Windows consoles the emoji in the startup log can raise a `UnicodeEncodeError`
in the log stream. It is cosmetic. Set `PYTHONIOENCODING=utf-8` rather than
changing application code.
