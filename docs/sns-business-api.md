# SNS business frontend API

Responses use `{"data": ..., "meta": {...}, "error": {}}`. Failures contain
`error.code` and `error.message`. Personal account/profile bookmarks retain
the separate contracts in `sns-frontend-api.md`.

## Public discovery

Base: `/api/services`, distinct from `/api/sns`. No login required.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/services/` | Search published listings. |
| GET | `/services/locations/` | Country/state/city choices and counts. |
| GET | `/services/categories/?country_code=DE` | All active two-level category choices, including empty branches. |
| GET | `/services/{service_id}/` | Published detail; missing/nonpublic returns the same 404. |
| GET | `/services/{service_id}/related-person/` | Privacy-filtered related person, or null when not permitted. No-store. |

Search accepts `q`, `country_code`, `state`, `city`, repeated `category` ids,
`persian_owned`, `persian_provider`, `persian_language`, `persian_service`,
`sort`, `page`, `size`. Relevance filters accept `yes`, `no`, `unknown`.
Pass `country_code=DE` for the German experience. Category matching includes
descendants. Unknown parameter names return 422. Pagination metadata has
`total`, `page`, `size`, `pages`.

Public objects contain id, name/description, location, nullable relevance
attributes, timestamps, visible business contacts and active categories. Owner
identifiers, `show_owner`, provenance, moderation status, hidden contacts and
contact database ids are excluded.

Location shape:

```json
[{"country_code":"DE","total":1,"states":[{"state":"Hessen","total":1,"cities":[{"city":"Frankfurt am Main","count":1}]}]}]
```

Category nodes contain `id`, `name`, `slug`, `level`, `parent_id`, `parent_ids`,
and `children`. Subcategories appear under every selected root, with one shared
ID. Search by any of those roots includes their businesses without duplicates.
See `business-taxonomy.md` for the migration, validation and starter data.

## Private saved businesses

Base: `/api/sns`. Requires the SNS bearer token.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/me/service-bookmarks` | Public business objects with `meta.total`; unpublished listings omitted. |
| POST | `/me/service-bookmarks/{service_id}` | Save a published business; duplicate requests succeed. |
| DELETE | `/me/service-bookmarks/{service_id}` | Remove it even after hiding; duplicate requests succeed. |

The account id always comes from authentication. Existing `/bookmarks` saves
people and is separate. Saving hidden/missing businesses returns the same
`SERVICE_NOT_FOUND` 404. Apply migration 17 before using these endpoints.

## Owner business management

Base: `/api/sns`. Requires the authenticated assigned owner.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/me/services?page=1&size=20` | Paginated assigned listings, including nonpublic states. |
| GET | `/me/services/{service_id}` | Editor data, including hidden business contacts. |
| PATCH | `/me/services/{service_id}` | Edit allowed customer-facing fields. |

PATCH requires `expected_updated_at` from the last read. It accepts name,
description, `owner_show_profile`, location and contacts. Omitted fields are preserved.
Explicit null clears nullable fields; name, `owner_show_profile`, contacts cannot be
null. `contacts: []` removes all contacts; a supplied list replaces them.
Contact fields: title, type, value, optional platform, display_order, is_visible.

Staff-controlled ownership, status, provenance, categories and relevance are
rejected as unknown input. Another account's listing returns the same 404 as a
missing one. Conflicting writes return 409 `CONFLICT_OCCURRED`; reload first.
Owner responses exclude provenance and owner id. `show_owner` remains a read-only
admin setting, also exposed as `admin_allows_owner_visibility`. Owners can edit
only their own `owner_show_profile` preference. Reassignment resets that consent
in the write repository and a database trigger (migration 20).

The public related-person endpoint requires all three: admin `show_owner`,
per-business `owner_show_profile`, and the person's global profile visibility.
It excludes banned people and applies existing per-field privacy before returning
only first/last name, bio, picture and supported contact links. No private owner
identifier is present when any gate is closed. The UI rechecks when opening its
person dialog; responses are not cached.

Personal visibility remains under `/account/privacy`: global discoverability
and existing per-field controls remain available in the API. The simplified
consumer presents one Private Profile setting; an explicit privacy save updates
global visibility and the limited visible fields. Normal edits do not republish
legacy private fields or erase hidden legacy data. Null privacy values return 422.
