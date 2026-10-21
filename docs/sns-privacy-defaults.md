# SNS privacy defaults and existing preferences

## Scope of this source change

Prepared locally on 2026-10-20. No database migration, live deployment or remote
change has been performed as part of this fix. Existing database rows have not
been inspected, restored or changed. Tests, builds and servers were not run.

The intended policy for **new privacy rows** matches the existing explicit
inserts in SNS login and channel synchronization:

| Setting | New-row default |
| --- | --- |
| Profile discoverable | true |
| Nickname, profile picture, country, bio, occupation | public |
| Username, first name, last name, phone, WhatsApp, social links | private |

These defaults apply only when a privacy row is created; they do not authorize
changing an existing user's settings. Login and channel synchronization use
`ON CONFLICT DO NOTHING` for privacy rows, retaining existing choices.

## Migration paths

- `scripts/database/20260826_11_set_sns_privacy_policy.sql` is corrected for
  installations that have not applied it: it now changes column defaults only.
  The unconditional update of existing visibility choices and `updated_at` is
  removed. The correction is explicitly recorded in the SQL comments.
- `scripts/database/20261020_22_preserve_sns_privacy_defaults.sql` provides the
  additive forward path for an installation with the existing SNS privacy
  schema. It changes only column defaults, preserves every existing row and
  timestamp, and can be rerun without changing stored preferences. It requires
  the occupation column introduced by the earlier SNS migrations.
- `app/models/user_privacy_settings.py` now declares the same defaults, so
  schemas created from ORM metadata agree with the migrated schema.

Migration 22 contains only a transaction and `ALTER COLUMN ... SET DEFAULT`
statements. It does not insert, backfill, update, delete, disable or re-enable
any profile. It does not touch the `updated_at` default or execute row updates.
Applying it still requires the normal reviewed migration procedure against the
intended target database; the SQL takes a table schema lock while it runs.

## Historical issue and recovery limits

The original migration 11 was committed in `753fdaa` on 2026-08-27 (its filename
is dated 2026-08-26). It unconditionally made all existing profiles discoverable,
set the five public fields above to public, set the remaining fields private,
and overwrote `updated_at`. This behavior predates the current local work.
Git history alone does not establish whether or when a deployed database ran it.

If that revision was already applied and committed, changing source code or
applying migration 22 cannot reconstruct earlier per-user choices. Recovery
requires trustworthy backups, point-in-time recovery data or audit evidence,
with a separate reconciliation plan preserving later legitimate user edits.
Migration 07 only fills missing privacy rows and cannot undo that reset.
Neither blanket private settings nor blanket public settings can recover the
individual choices that were lost; no inferred restoration is included here.
