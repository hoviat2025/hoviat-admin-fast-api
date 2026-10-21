# SNS product direction

Agreed with the product owner on 2026-10-16.

## Initial product

SNS helps people discover businesses and services connected to the Persian
community, starting in Germany. People browse/search, inspect business details
and public contact methods, and save businesses to a private list.

Persian ownership, provider, language support and service relevance are four
independent tri-state attributes. Unknown must not be presented as a negative
assessment. Location is a separate dimension.

Account holders control personal profile discovery and individual name/contact
visibility. Assigned owners maintain customer-facing business information and
choose which business contacts are public. Publishing a business must not
automatically disclose a personal account or phone number.

Posts and broader social interactions are future possibilities outside this
initial product. Accounts, businesses and bookmarks remain separate concepts
so future features can extend them without changing their meaning.

## Roles and journeys

| Role | Initial journey |
| --- | --- |
| Visitor | Search published businesses by text, category and location; open details and use visible contact methods. |
| Signed-in account | Maintain personal profile/privacy and save/remove businesses. |
| Assigned owner | Edit assigned business information/contact visibility and detect conflicting edits. |
| Staff | Create/curate listings, assign ownership, manage categories/relevance and publish/hide/archive. |

Ownership assignment is currently performed by staff. Self-claiming listings
and owner-controlled publication need review rules before being added.

## Application locations

- FastAPI backend: `hovait-fastapi`.
- Active admin frontend: `admin-panel-front/lumina-admin` (Vite/React).
- Latest consumer prototype: `sns/hoviat-nextjs-notion-09/discover-app`
  (Next.js/React). Earlier numbered copies and `hoviat-panel-nextjs` are older
  prototypes/admin code; they do not implement business discovery.

## Completion criteria

1. Staff can create, categorize, assign and publish a listing in the admin UI.
2. Visitors can find published businesses and open details. Draft, hidden and
   archived listings are unavailable through public reads.
3. Hidden contacts and personal owner identifiers never appear in public search,
   business detail or bookmark responses. A separate related-person projection
   is available only with staff permission, that person's per-business consent
   and a public personal profile; existing field privacy still applies.
4. Saved businesses are private to each authenticated account. Unpublished
   listings disappear from saved results.
5. Owners edit their listings without changing staff-controlled fields. Stale
   writes return a conflict rather than overwriting newer changes.
6. Personal privacy controls work independently and reject invalid values
   before persistence.
7. Frontend builds and representative backend/database journeys pass locally
   before deployment.

See `sns-business-api.md` for consumer integration and `local-development.md`
for disabled background workers. Deployment includes the additive bookmark
migration. Website privacy does not revoke previously shared public image URLs
or rewrite existing Telegram publications.

The 2026-10-18 usability update adds a two-level category vocabulary with shared
subcategories/one primary root, guided contacts, simplified personal profile
editing and one global Private Profile option. Admins manage category roots and
placements; end users edit their profile and assigned businesses in bounded
dialogs. See `business-taxonomy.md` for migrations 19/20 and the local starter seed.
