# Business directory

This domain owns services, categories, business contacts and country/state
vocabulary. A business is separate from a personal SNS account. Germany is the
initial presentation default; the data model uses international country codes.

## Entry points

- Staff administration: `/api/admin/service-management`.
- Public discovery: `/api/services/services/`, `locations/`, `categories/`,
  and `{service_id}/`.
- Assigned owners: `/api/sns/me/services` and `/{service_id}`.
- Private business bookmarks: `/api/sns/me/service-bookmarks` and `/{service_id}`.

See [the API guide](../../../docs/sns-business-api.md) and
[the product direction](../../../docs/sns-product.md).

## Visibility and permissions

Public reads return published listings through a dedicated projection, visible
business contacts and active category labels. Import provenance, moderation
status and personal owner associations are excluded. `show_owner` alone never
authorizes revealing a personal account.

Staff control publication, ownership assignment, categories and relevance.
Authenticated assigned owners may edit customer-facing business fields and
contact visibility using a required `expected_updated_at` token. Ownership is
checked under a row lock before writes; passing a listing id cannot claim it.
Owner responses include hidden business contacts for editing, but no provenance.

Personal profile/name/phone visibility remains under SNS account privacy and is
independent of business contact visibility.

SQL migration 17 adds business bookmarks separately from profile bookmarks.
Domain writes share validation and transactional aggregate saves. Public reads
never reuse staff response objects.
