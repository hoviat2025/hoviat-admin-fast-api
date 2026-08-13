# Internal cron synchronization

The Ubuntu server scheduler must call:

```text
POST /webhook/hoviat/v1/cron-sync
X-Cron-Secret: <the value configured in CRON_SYNC_SECRET>
```

Set `CRON_SYNC_SECRET` in the server's environment or `.env` file. Do not put
the secret in a URL query parameter, source code, or logs. The endpoint returns
`401` when the header is missing or incorrect.

Example server-side cron command:

```bash
curl --fail-with-body --silent --show-error \
  -X POST \
  -H "X-Cron-Secret: ${CRON_SYNC_SECRET}" \
  https://127.0.0.1/webhook/hoviat/v1/cron-sync
```

The scheduler should load `CRON_SYNC_SECRET` from the same protected service
environment used by the API process.
