# Directory imports

Scope: business directory only. No changes to Eurobot, Hilfen, Telegram workers,
user accounts, profile privacy or authentication.

## Admin workflow

Open **Businesses → Import JSON**. Choose either:

- **Businesses and categories**: select extraction files. The browser merges the
  bundled starting catalogue with every file's `category_suggestions`, including
  categories with no attached business. It imports categories first, then businesses.
- **Categories only**: select catalogue JSON files or extraction files. No
  businesses are imported. The **Use starting catalogue** button loads the bundled
  11 groups and 141 categories. Export the prepared catalogue to keep or extend it.

Both modes require preview before apply. Preview does not persist rows (PostgreSQL
ID sequences may advance). Existing matching categories are reused; import never
renames, reparents, reactivates or deletes them. Conflicting names, memberships,
unknown parents and third-level categories stop the affected category batch.
Nothing from business batches is sent until the category phase succeeds.

Categories are matched by stable `key` (database `slug`), never by numeric IDs.
Keys normalize to lowercase hyphenated identifiers, matching existing slug rules.
Identical definitions across selected files merge. Conflicting definitions fail
local preparation. A child can belong to several first-level groups, with one
primary parent. Businesses can select only second-level categories.

### Standalone JSON format

```json
{
  "schema_version": "1.0",
  "parents": [{"key": "health", "name": "خدمات پزشکی و سلامت"}],
  "categories": [{
    "key": "orthodontics",
    "name": "ارتودنسی",
    "primary_parent_key": "health",
    "parent_keys": ["health"]
  }]
}
```

Parents can be omitted if they already exist in the target database. Database IDs
are generated; description is optional and defaults to null, display order to 0,
active status to true. Do not invent additional category information.

### Requests and interruption

- `POST /api/admin/service-management/imports/categories`: admin write permission;
  `{preview, definitions, keys}`. Up to 500 definitions, 25 requested keys per
  request, 2 MB. A category batch is transactional, including its audit entries.
- Business endpoint stays `/imports/businesses`, up to 10 records per request.
- The browser controls batching and reports category and business results.
- Retry by previewing again: committed categories/businesses are reused/skipped.
- Category batches may already be committed if a later batch fails. Business
  records are committed individually. A whole multi-file import is not atomic.
- Business update mode still preserves owner, privacy preference, photo and
  publication status, with stale-preview protection.

## One-time reset: separate from imports and migrations

`scripts/deployment/reset_directory_20261125.py` is an explicit VPS command, never
an admin button and never run on application startup. Start with its read-only
preview, using sudo and the intended database name:

```bash
sudo python3 scripts/deployment/reset_directory_20261125.py --database hoviat_sns_stage_20261021
```

After reviewing counts, an explicit apply uses:

```bash
sudo python3 scripts/deployment/reset_directory_20261125.py --database hoviat_sns_stage_20261021 --apply --confirm "EMPTY DIRECTORY IN hoviat_sns_stage_20261021"
```

The production database name is `hoviat`; use that name only for the deliberately
authorized production reset after staging validation. The script saves a private
full `pg_dump` before deleting anything. It locks the directory tables and clears
businesses, their contacts/category links/bookmarks, category parent links and
categories in one transaction, using DELETE without TRUNCATE CASCADE. Lock failure
aborts rather than waiting indefinitely. Required directory migrations must exist.

Users, profile bookmarks, locations, Telegram IDs, jobs and audit history remain.
R2 objects are not deleted; removed businesses' cover-image objects may remain
unreferenced. No sequence IDs are reset. Full-database backup restoration would
overwrite newer unrelated writes, so plan a selective directory recovery if needed.
The backup precedes the delete transaction; avoid directory edits during reset.

No reset is executed by adding these files or deploying this code.
