"""
Service-directory domain.

This module owns the `services`, `categories`, `service_categories` and
`service_contacts` tables. It is intentionally separate from the user (SNS)
domain: the public product searches services, not people.

Scope of the current milestone
------------------------------
Milestone 1 provides the data foundation only: models, the SQL migration,
validation and the repository/service layer. There are no HTTP routes yet.

  * Milestone 2 wires admin CRUD on top of these services.
  * Milestone 4 adds the public service-search repository/service.
  * Milestone 5 adds the discovery/search frontend.

Permission assumptions (unchanged for now)
------------------------------------------
  * Only staff admins (the admin JWT, see app/modules/admin) may create or edit
    services.
  * `owner_user_id` is a data association, not an authorization grant. It does
    not, by itself, let a user edit the service.
  * `show_owner` controls public display of the owner, but public display also
    requires the owner's own privacy settings to allow it. That combination is
    enforced by the read layer when the public pages are built (Milestone 3).
"""
