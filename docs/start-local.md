# Start SNS locally

Start these in order, each in a separate PowerShell terminal. Leave each running.
PostgreSQL must be running: the API uses the local database
`hoviat_service_dev` on port 5433. Background workers are disabled in local `.env`.

## 1. API — port 18743

```powershell
cd "C:\Users\asus\Projects\hoviat\hovait-fastapi"
.\.venv\Scripts\Activate.ps1
python run.py
```

API docs: [http://127.0.0.1:18743/docs](http://127.0.0.1:18743/docs).

## 2. Admin panel — port 18744

No Python environment needed.

```powershell
cd "C:\Users\asus\Projects\hoviat\admin-panel-front\lumina-admin"
npm run dev
```

Open [http://127.0.0.1:18744](http://127.0.0.1:18744).

## 3. User panel — port 18745

No Python environment needed.

```powershell
cd "C:\Users\asus\Projects\hoviat\sns\hoviat-nextjs-notion-09\discover-app"
npm run dev
```

Open [http://127.0.0.1:18745/discover](http://127.0.0.1:18745/discover).

Both frontends point to the API on port 18743. These ports are fixed local
defaults; the admin exits if its port is occupied rather than silently choosing
another one. Press Ctrl+C in each terminal to stop its server.

## User-panel development login

The backend `.env` can enable a code-free local SNS test account:

```env
DEV_LOGIN_ENABLED=true
```

Restart the API after changing this setting. The user-panel login page then
shows **ورود توسعه بدون کد** with a user-ID input. Enter an existing local user's
ID to sign in as that user, or leave it blank for the dedicated development
account. Unknown IDs and banned accounts are refused. Switching identities
reloads the frontend to clear the previous user's private client state.
Login makes no Telegram requests or queued channel-sync jobs. No frontend environment
flag is needed. Set it to `false` and restart the API to disable the option.
It is enabled in the current local `.env`; the application default is disabled.

This option requires the local API/database and disabled background workers.
It does not bypass admin-panel authentication. Dev sessions use a separate
derived signing key and a dev marker, and are accepted only on the guarded local
API while this option remains enabled. Disabling it rejects already issued dev
sessions as well. This feature does not import production users into the local DB.

## Support invitation in the user panel

The homepage and the empty My Businesses screen open a shared contact modal
with Telegram and phone contact rows. Set real contacts in the consumer's
`.env.local` and restart the user
panel (rebuild for production):

```env
NEXT_PUBLIC_SUPPORT_TELEGRAM_URL=https://t.me/your_real_support_username
NEXT_PUBLIC_SUPPORT_PHONE=+49...
```

These examples must be replaced with actual public contacts. Until valid values
are configured, each row displays a clearly marked, non-clickable placeholder.
Both invitations share `lib/support-contacts.ts` in the active consumer; its
comments and `.env.example` document how to replace the placeholders. No login
bot fallback is used. These are public contacts, not secrets.

Start the projects manually when needed. These commands use local code and
the local development database. Outbound Telegram login/media integrations
still use their configured services; disabling workers only stops queue workers.
