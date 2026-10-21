# Two-level business taxonomy

Categories have exactly two possible levels. Level 1 is a root without parents.
Level 2 is a child that belongs to one or more roots. A child cannot itself be a
parent. Its primary root remains in `categories.parent_id`, while all root
memberships are stored in `category_parents`. Category IDs used to assign
businesses remain independent of the number of root memberships.

## API contract

Existing admin category routes are unchanged. Category responses now include:

```json
{"id": 42, "level": 2, "parent_id": 1, "parent_ids": [1, 8]}
```

`parent_ids` is complete and lists the primary parent first. Roots return
`level: 1`, `parent_id: null`, and `parent_ids: []`.

Create/update requests accept optional `level`, `parent_ids`, and `parent_id`.
The new editor should send all three. A supplied `parent_id` must be a member of
`parent_ids`; if omitted, an existing valid primary is preserved or the first
supplied root is selected. Omitted hierarchy fields preserve the current
hierarchy. For old clients, a `parent_id`-only update replaces the membership
set with that single root, or clears it when null. Level must agree with the
resulting membership set.

Self-parenting, non-root parents, and inconsistent levels return 422. A missing
parent returns 404. A root with children cannot become a child until those
children have been moved; this returns 409. Category mutations use a shared
transaction advisory lock and deterministic category row locks. Deferred
PostgreSQL constraints also enforce the structural rules at commit, including
changes outside the API.

Admin tree responses include the same child ID under every root membership.
Flat admin lists contain one row per category. Public category trees expose all
active root/child branches, even when no businesses have been published. Their
`country_code` parameter remains accepted and validated; the taxonomy itself is
shared across countries and does not report invented business counts.

Filtering by a root matches businesses assigned to a child under **any** of its
root memberships. Shared children, multiple category filters, and multiple
business category assignments do not duplicate businesses or inflate totals.

## Migration 19

Apply `scripts/database/20261018_19_category_root_memberships.sql` before using
the new backend. It adds the membership table/index and structural constraints.
Existing primary parents are backfilled. An existing deeper category keeps its
ID and business assignments, but is moved directly under its top root so the
result has two levels. Existing cycles cause the migration to stop and roll
back rather than guess a repair. Existing secondary memberships are preserved
on a normal rerun; invalid memberships cause a rollback.

Migrations 19 and 20 and the starter seed were applied on 2026-10-18 only to the
guarded local `127.0.0.1:5433/hoviat_service_dev` database, with workers disabled.
The seed committed eight roots and 32 children, preserving business assignments.
Production and other databases require their own migration step. Migration 20 contains the
separate owner-public-profile consent change; apply it as well before starting
the complete backend version.

## Guarded local starter seed

The script only accepts the configured database
`127.0.0.1:5433/hoviat_service_dev` with background workers disabled. Before any
write, it checks PostgreSQL's current database name and loopback server address.
Its default command only prints a plan:

```powershell
rtk proxy .venv\Scripts\python.exe scripts/database/seed_local_business_taxonomy.py
```

Review that plan, then apply it locally:

```powershell
rtk proxy .venv\Scripts\python.exe scripts/database/seed_local_business_taxonomy.py --apply
```

The script creates/reuses eight roots and 32 starter children. Roots cover food,
health, legal/administrative/financial services, home/property, beauty,
education, events/culture, and shopping/daily services. Shared categories include
catering under food/events, translation under professional services/education,
photography under events/daily services, and beauty clinics under beauty/health.

Existing exact canonical slugs keep their IDs. If absent, an explicit known slug
alias or normalized exact Persian name is reused. Arabic/Persian letter variants
and spacing are normalized for these exact names; there is no fuzzy matching of
unrelated categories. The full reviewed alias/name map is the `ROOTS` and
`CHILDREN` data at the top of the script.

| Existing starter slug | Curated destination |
| --- | --- |
| `food`, `healthcare`, `professional-services`, `beauty` | Same root IDs, clearer Persian labels |
| `restaurant`, `catering`, `grocery-store`, `bakery`, `doctor`, `dentist`, `clinic`, `lawyer`, `accountant`, `translator`, `real-estate`, `hairdresser`, `repair-service` | Same IDs; curated labels/root memberships |
| `automotive` | Reused as `car-services`, a child of shopping/daily services |
| Children formerly under `automotive` | Moved to its resulting root memberships, preserving their IDs |
| Known duplicates such as `restaurants` / `restaurant` or `dentists` / `dentist` | Canonical category, with every old-ID-to-new-ID merge printed |

Duplicate consolidation moves business category assignments to the canonical
ID, coalesces duplicate links and preserves the primary flag. Child memberships
are rewired before deleting a now-unreferenced duplicate. The script verifies
the entire assignment/primary mapping before commit and advances version tokens
on businesses whose category assignments changed. Old external category URLs
that refer to a merged ID should be updated using the printed merge map.

Existing custom categories and valid extra root memberships are retained. An
existing valid primary is preserved; new children use the first curated root.
Curated labels, ordering, active status and required cross-links are maintained
by the seed. A rerun does not create duplicate categories or assignments. All
changes occur in one transaction; errors roll back the whole seed. It does not
create businesses, modify personal accounts or fabricate published listings.
