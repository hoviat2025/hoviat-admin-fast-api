# SNS business duplicates — 2026-11-27

This is an admin-only directory feature. No Telegram, queue, user or other module
behavior is changed. No AI service, key or automatic AI execution is added.

## Workflow

Open **Businesses → Duplicate management** (`/services/duplicates`).

1. Download the compact JSON and matching prompt. Optional city and first-level
   category filters can be combined; leave both empty to export everything.
2. Give both files to one AI. Import its JSON result into the same admin screen.
3. Preview, compare the complete records and proposed changes, and optionally
   download the JSON/text report. This step never writes business data.
4. Select reviewed likely groups and confirm the merge. Possible groups cannot
   be applied; if staff confirm one, change its confidence in the proposal file
   to `likely` and preview the file again.
5. Retrieve removed records from the private archive section at any time.

The downloadable prompt lives at
`admin frontend/src/data/business-duplicates-prompt.txt`. Output uses:

```json
{"schema_version":"1.0","groups":[{"keep_id":42,"remove_ids":[17],"confidence":"likely","reason":"نام، نشانی و تلفن یکسان؛ رکورد ۴۲ کامل‌تر است."}]}
```

Each ID occurs in only one group, at most 20 records per group. The AI suggests
the more complete keeper, then later creation date (import date, not a verified
source update date). It receives no full descriptions, source text or ownership
data. A full-record preview is mandatory, but a second AI is not required.

## Cost and limits

The browser requests 200 compact records at a time using ID-based pagination.
The server permits at most 500 per request and slices descriptions to 120
characters in SQL. Contacts are fetched for that page in one additional query;
there is no per-row query loop. No raw import JSON or media is read for export.
A fixed maximum ID excludes newly inserted records during that export. This
is not a database snapshot: edits during a long export can still be reflected.
Merge preview uses fresh full records and independently checks for stale data.

The browser downloads one JSON file, holding up to 25 MiB of compact records in
memory. If exceeded, it asks staff to narrow the optional filters and does not
download an incomplete file. AI response files are limited to 2 MiB/2,000 groups;
preview requests contain at most 20 groups and apply requests one group each.
Filters can miss duplicates with different city/category assignments. They are
an optional way to divide work, not a guarantee of global duplicate detection.

## Merge and archive rules

- Transactions are per group. Failure rolls back that entire group, including
  its archive and audit entries. Earlier completed groups remain completed.
- Service rows are locked; preview hashes cover full records, categories,
  contacts and bookmarks. Apply rejects a stale/missing preview. The same import
  advisory lock serializes import and merge operations.
- The keeper's nonempty fields, publishing state, ownership/privacy and primary
  category remain unchanged. Only missing descriptions/original description/
  cover image are filled, plus contacts and secondary category memberships.
  Location components are not mixed from potentially conflicting addresses.
- Different owners or visibility preferences block that group. Conflicting
  nonempty content is shown in preview; the keeper wins, and the other values
  remain in the archived snapshot. The AI's reason is never used as executable
  instructions or database field assignments.
- Bookmarks move to the keeper without duplication, retaining the earliest
  existing bookmark time. No media files are deleted or copied.
- Removed rows leave the active tables. `service_duplicate_archives` stores all
  their columns, import/source data, contacts, categories, bookmarks and the
  keeper before the merge. This archive consumes disk space but does not enter
  normal listings, counts or exports. It is accessible only to authorized staff.
- The archive is a retained data snapshot, not a one-click undo feature. It can
  be downloaded for recovery; reversing later edits would require reconciliation.
- Archived source identities prevent both add and update imports from recreating
  a duplicate. Import reports the survivor and skips it. If a survivor is merged
  later, earlier archive references follow the new survivor. If the survivor is
  deleted separately, the archive and source identity remain preserved.
- A repeated successful group is reported as already applied. Groups overlapping
  a different earlier merge are rejected for fresh review.

## Deployment

Deploy backend and admin frontend together after staging verification. Apply the
additive migration `scripts/database/20261127_25_business_duplicates.sql` using
the directory database's owning role before starting the new backend. It creates
only the archive table/index, changes no existing data and performs no merges.
The importer now reads that table, so the migration is required even before the
first merge. No environment, Cloudflare or consumer frontend change is needed.

New endpoints under `/api/admin/service-management/duplicates`:
`GET /export`, `POST /merge`, `GET /archive`, `GET /archive/{original_id}`.
All use the existing administrator write permission. No public archive endpoint.

Tests in `tests/test_business_duplicates.py` opt into a **local development/test
database** with `BUSINESS_IMPORT_TEST_DB_URL` and create/drop isolated schemas.
Never point these tests at a production database.
