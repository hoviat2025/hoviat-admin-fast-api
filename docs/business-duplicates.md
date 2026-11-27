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
4. Select reviewed likely groups and confirm keeping the chosen record and
   archiving/removing the others. There is no field-combining step. Possible groups cannot
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

## Keep-one and archive rules

- Transactions are per group. Failure rolls back that entire group, including
  its archive and audit entries. Earlier completed groups remain completed.
- Service rows are locked; preview hashes cover full records, categories,
  contacts and bookmarks. Apply rejects a stale/missing preview. The same import
  advisory lock serializes import and merge operations.
- The chosen keeper stays entirely unchanged: no descriptions, contacts,
  categories, media paths, location fields or timestamps are copied or modified.
  Choose the more complete record first, then the most recently updated record
  (creation time if update time is unavailable).
  That choice is made by the AI and reviewed by staff, not silently overridden
  by a second ranking algorithm on the server.
- Different owners or owner visibility preferences still block that group.
  Removed records' differing values remain only in their archived snapshots.
  The AI's reason is never used as executable
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
- Preview tokens include the keep-only policy version, so an old preview showing
  field combination cannot accidentally authorize this changed behavior.

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

## Optional incremental, multi-session review

The export UI can accept **previously checked through** (device-local time,
converted to UTC) and a maximum number of records per AI file (default 300).
Leaving the option off preserves the ordinary single-file full review.

`max(created_at, updated_at) > cutoff` identifies new/edited records; the exact
cutoff belongs to the old baseline. The cutoff is an administrator's statement
about previous checking, not a stored/computed certification. No export, import
or preview advances it automatically. A city/category review applies only to
that scope, so its cutoff must not later be treated as a global checkpoint.

An incremental export downloads ONE ZIP containing a manifest, the prompt and
numbered JSON parts. All new records appear in every part. Old baseline records
are divided between the remaining spaces, so every new-old comparison is
represented once. Only part 1 asks for new-new comparisons. Old-old comparisons
are deliberately skipped; this mode assumes that baseline was checked already.
This arrangement partitions the requested comparison work, not the guarantee
that a probabilistic AI will detect every match.

The entire new set must fit in one part, with at least one additional place when
old records exist. Otherwise the UI asks for a larger per-file limit or narrower
filters; it never silently splits new records and loses cross-new comparisons.
The original 25 MiB browser/export safeguard remains, including repeated copies
of new records in the ZIP. No new package dependency or migration is introduced.
Reading remains paginated, and export labels do not write to the database.

Use a separate AI session for each part plus the prompt. Each result copies
`export_id`, `part_number`, `total_parts` alongside `schema_version` and `groups`.
Collect all results (including empty groups) and select them together in the
multi-file result input. Incomplete numbered sets can be previewed but not
applied. Mixed export IDs/part totals and duplicate part numbers are rejected.
Existing single-file, non-partitioned proposals remain supported.

Identical repeated suggestions are deduplicated. Other overlaps are grouped
for **review only**, with their original proposals retained in the report.
There is no automatic transitive merge or automatic keeper selection across
sessions. Staff see full records, explicitly confirm that all represent one
entity, choose the keeper and receive a new preview. They then use the existing
selection/approval action. Possible matches can be confirmed in the same UI
without editing JSON or requiring another AI. Overlap components above 20 members
are rejected for separate handling rather than generating overlapping deletions.

After ALL parts and findings are handled, staff can use the manifest's export
start time as the next checkpoint for that same scope. Pages are not a frozen
database snapshot: records created or edited during/after the export remain new
at that checkpoint and must be checked on the next run.
