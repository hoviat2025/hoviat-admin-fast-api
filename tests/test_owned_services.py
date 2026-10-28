"""Owner authorization, privacy boundaries, and inherited concurrency rules.

SQLite exercises the actual ownership filters and eager relationship loading;
PostgreSQL compilation verifies the read locks SQLite does not implement.
Writes use fake repositories to prove denial happens before any mutation and
that the existing aggregate transaction remains responsible for version checks.
"""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pydantic import ValidationError
from sqlalchemy import create_engine, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, raiseload

from app.core.exceptions import ServiceError
from app.models.base import Base
from app.models.category import Category
from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact
from app.modules.services.schemas.service_responses import ServiceResponse
from app.modules.services.repositories.service import ServiceRepository
from app.modules.sns.owned_services.schemas import (
    OwnedServiceResponse,
    OwnedServiceUpdateRequest,
)
from app.modules.sns.owned_services.service import OwnedServiceService


NOW = datetime(2026, 10, 16, 12, 0, 0, 123456, tzinfo=timezone.utc)


def current_service():
    return ServiceResponse(
        id=11, owner_user_id=40, name="Praxis", description="Business bio",
        show_owner=False, status="hidden", country_code="DE", state="Hessen",
        source="staff-import", external_id="private-source-123",
        persian_owned=False, persian_provider=True, persian_language=None,
        persian_service=False, created_at=NOW, updated_at=NOW,
        contacts=[dict(
            id=7, title="Private business contact", type="phone", value="+4912345",
            platform=None, display_order=2, is_visible=False,
        )],
        categories=[dict(
            category_id=5, is_primary=True,
            category=dict(id=5, name="Health", slug="health"),
        )],
    )


class OwnerRequestTests(unittest.TestCase):
    def test_staff_fields_and_owner_assignment_cannot_be_injected(self):
        forbidden = {
            "owner_user_id": 40, "status": "published", "source": "mine",
            "external_id": "123", "categories": [], "relevance": {},
            "persian_owned": True, "persian_provider": True,
            "persian_language": True, "persian_service": True,
            "user_id": 99, "privacy": {},
        }
        for field, value in forbidden.items():
            with self.subTest(field=field), self.assertRaises(ValidationError):
                OwnedServiceUpdateRequest.model_validate({
                    "expected_updated_at": NOW, field: value,
                })

    def test_null_required_fields_are_rejected_but_omission_is_allowed(self):
        for field in ("name", "show_owner", "contacts"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                OwnedServiceUpdateRequest.model_validate({
                    "expected_updated_at": NOW, field: None,
                })
        payload = OwnedServiceUpdateRequest(expected_updated_at=NOW)
        self.assertEqual(payload.model_fields_set, {"expected_updated_at"})

    def test_nullable_business_fields_can_be_explicitly_cleared(self):
        payload = OwnedServiceUpdateRequest(
            expected_updated_at=NOW, description=None, country_code=None,
            state=None, address=None, latitude=None, longitude=None,
        )
        self.assertIn("description", payload.model_dump(exclude_unset=True))
        self.assertIsNone(payload.description)

    def test_version_token_is_required_non_null_and_parseable(self):
        for data in ({}, {"expected_updated_at": None}, {"expected_updated_at": "bad"}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                OwnedServiceUpdateRequest.model_validate(data)

    def test_contact_rows_cannot_inject_database_ids(self):
        with self.assertRaises(ValidationError):
            OwnedServiceUpdateRequest(
                expected_updated_at=NOW,
                contacts=[dict(id=8, title="Email", type="email", value="a@b.de")],
            )

    def test_owned_response_excludes_import_metadata_and_owner_identity(self):
        response = OwnedServiceResponse.from_service(current_service()).model_dump()
        for field in ("source", "external_id", "owner_user_id"):
            self.assertNotIn(field, response)
        self.assertFalse(response["contacts"][0]["is_visible"])


class OwnerWriteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(commit=AsyncMock())
        self.service = OwnedServiceService(self.db)
        self.row = SimpleNamespace(owner_user_id=40, updated_at=NOW)
        self.domain = self.service.domain
        self.domain.services = SimpleNamespace(
            get_for_update=AsyncMock(return_value=self.row),
            update=AsyncMock(), exists_external=AsyncMock(return_value=False),
        )
        self.domain.get = AsyncMock(return_value=current_service())
        self.domain.contacts.replace = AsyncMock()
        self.domain.category_links.replace = AsyncMock()
        self.service.get = AsyncMock(
            return_value=OwnedServiceResponse.from_service(current_service())
        )

    async def test_missing_unassigned_and_other_owner_are_identical_404_without_write(self):
        for row in (None, SimpleNamespace(owner_user_id=None), SimpleNamespace(owner_user_id=99)):
            with self.subTest(row=row):
                self.domain.services.get_for_update.return_value = row
                with self.assertRaises(ServiceError) as caught:
                    await self.service.update(40, 11, OwnedServiceUpdateRequest(
                        expected_updated_at=NOW, description="Changed",
                    ))
                self.assertEqual(caught.exception.status_code, 404)
                self.assertEqual(caught.exception.code, "SERVICE_NOT_FOUND")
        self.domain.get.assert_not_awaited()
        self.domain.contacts.replace.assert_not_awaited()
        self.domain.category_links.replace.assert_not_awaited()
        self.domain.services.update.assert_not_awaited()
        self.db.commit.assert_not_awaited()

    async def test_owner_lock_precedes_read_save_and_response_authorization(self):
        events = []

        async def lock(_):
            events.append("lock")
            return self.row

        async def read(_):
            events.append("read")
            return current_service()

        async def save(*_, owner_show_profile):
            self.assertIsNone(owner_show_profile)
            events.append("save")

        async def response(*_):
            events.append("authorize_response")
            return OwnedServiceResponse.from_service(current_service())

        self.domain.services.get_for_update.side_effect = lock
        self.domain.get.side_effect = read
        self.domain.save_aggregate = AsyncMock(side_effect=save)
        self.service.get.side_effect = response
        await self.service.update(40, 11, OwnedServiceUpdateRequest(
            expected_updated_at=NOW, description="New biography",
        ))
        self.assertEqual(events, ["lock", "read", "save", "authorize_response"])

    async def test_partial_bio_edit_preserves_staff_fields_and_omitted_contacts(self):
        self.domain.save_aggregate = AsyncMock()
        await self.service.update(40, 11, OwnedServiceUpdateRequest(
            expected_updated_at=NOW, description=None,
        ))
        service_id, saved = self.domain.save_aggregate.await_args.args
        self.assertEqual(service_id, 11)
        self.assertIsNone(saved.description)
        self.assertEqual(saved.name, "Praxis")
        self.assertEqual(saved.owner_user_id, 40)
        self.assertEqual(saved.status, ServiceStatus.hidden)
        self.assertEqual((saved.source, saved.external_id), ("staff-import", "private-source-123"))
        self.assertEqual(
            (saved.persian_owned, saved.persian_provider, saved.persian_language, saved.persian_service),
            (False, True, None, False),
        )
        self.assertEqual(saved.categories[0].model_dump(), {"category_id": 5, "is_primary": True})
        self.assertFalse(saved.contacts[0].is_visible)
        self.assertNotIn("id", saved.contacts[0].model_dump())
        self.assertEqual(saved.expected_updated_at, NOW)

    async def test_empty_contact_array_explicitly_removes_contacts(self):
        self.domain.save_aggregate = AsyncMock()
        await self.service.update(40, 11, OwnedServiceUpdateRequest(
            expected_updated_at=NOW, contacts=[],
        ))
        self.assertEqual(self.domain.save_aggregate.await_args.args[1].contacts, [])

    async def test_stale_timestamp_inherits_aggregate_409_before_any_write(self):
        with self.assertRaises(ServiceError) as caught:
            await self.service.update(40, 11, OwnedServiceUpdateRequest(
                expected_updated_at=NOW - timedelta(seconds=1), description="stale",
            ))
        self.assertEqual(caught.exception.status_code, 409)
        self.domain.contacts.replace.assert_not_awaited()
        self.domain.category_links.replace.assert_not_awaited()
        self.domain.services.update.assert_not_awaited()
        self.db.commit.assert_not_awaited()
        self.service.get.assert_not_awaited()

    async def test_millisecond_token_reaches_existing_aggregate_commit(self):
        # Keep the real save_aggregate and _finish implementations; only replace
        # validation/database collaborators unrelated to the version check.
        self.domain._service_data = AsyncMock(return_value={"source": None, "external_id": None})
        self.domain._ensure_owner_exists = AsyncMock()
        self.domain._validate_category_state = AsyncMock()
        await self.service.update(40, 11, OwnedServiceUpdateRequest(
            expected_updated_at=NOW.replace(microsecond=123000), description="new",
        ))
        self.domain.contacts.replace.assert_awaited_once()
        self.domain.category_links.replace.assert_awaited_once()
        self.domain.services.update.assert_awaited_once()
        self.db.commit.assert_awaited_once()
        self.service.get.assert_awaited_once_with(40, 11)

    async def test_reassignment_after_commit_denies_response(self):
        self.domain.save_aggregate = AsyncMock(return_value=current_service())
        self.service.get.side_effect = ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
        with self.assertRaises(ServiceError) as caught:
            await self.service.update(40, 11, OwnedServiceUpdateRequest(expected_updated_at=NOW))
        self.assertEqual(caught.exception.status_code, 404)
        self.domain.save_aggregate.assert_awaited_once()


class _AsyncReadSession:
    """Real ORM reads with implicit lazy loads forbidden, like an async session."""

    def __init__(self, session):
        self.session = session
        self.statements = []

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def execute(self, statement):
        self.statements.append(statement)
        return self.session.execute(statement.options(raiseload("*")))


class OwnerReadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine, tables=[
            Service.__table__, Category.__table__, ServiceContact.__table__, ServiceCategory.__table__,
        ])
        self.session = Session(self.engine, expire_on_commit=False)
        self.session.add(Category(id=5, name="Health", slug="health"))
        for service_id, owner in ((11, 40), (12, 99), (13, None), (14, 40)):
            self.session.add(Service(
                id=service_id, owner_user_id=owner, name=f"Service {service_id}",
                show_owner=False, status=ServiceStatus.hidden,
                source="private-import", external_id=str(service_id),
                created_at=NOW, updated_at=NOW,
                contacts=[ServiceContact(
                    id=service_id, title="Private", type="phone", value="+49123",
                    is_visible=False, display_order=0,
                )],
                category_links=[ServiceCategory(category_id=5, is_primary=True)],
            ))
        self.session.commit()
        self.session.expunge_all()
        self.db = _AsyncReadSession(self.session)
        self.service = OwnedServiceService(self.db)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def test_list_filters_ownership_counts_and_pages_in_stable_order(self):
        first, total = await self.service.list(40, page=1, size=1)
        second, second_total = await self.service.list(40, page=2, size=1)
        self.assertEqual((total, second_total), (2, 2))
        self.assertEqual([item.id for item in first + second], [14, 11])
        self.assertEqual(first[0].status, ServiceStatus.hidden)
        self.assertFalse(first[0].contacts[0].is_visible)
        self.assertEqual(first[0].categories[0].category.name, "Health")

    async def test_unknown_owner_gets_empty_list(self):
        items, total = await self.service.list(123, page=1, size=20)
        self.assertEqual((items, total), ([], 0))

    async def test_get_rejects_unknown_unassigned_and_other_owned_rows(self):
        for service_id in (12, 13, 999):
            with self.subTest(service_id=service_id), self.assertRaises(ServiceError) as caught:
                await self.service.get(40, service_id)
            self.assertEqual(caught.exception.status_code, 404)

    async def test_get_eagerly_loads_private_contacts_and_categories(self):
        response = await self.service.get(40, 11)
        self.assertEqual(response.contacts[0].value, "+49123")
        self.assertFalse(response.contacts[0].is_visible)
        self.assertEqual(response.categories[0].category.slug, "health")
        self.assertNotIn("source", response.model_dump())

    async def test_new_listing_person_preference_starts_on(self):
        response = await self.service.get(40, 11)
        self.assertTrue(response.owner_show_profile)
        # Admin permission remains independent of the new person preference.
        self.assertFalse(response.admin_allows_owner_visibility)

    async def test_same_owner_assignment_preserves_an_explicit_opt_out(self):
        repo = ServiceRepository(self.db)
        await repo.update(11, {"owner_show_profile": False})
        row = await repo.update(11, {"owner_user_id": 40, "name": "Updated business"})
        self.assertFalse(row.owner_show_profile)

    async def test_new_person_assignment_uses_the_new_visible_preference(self):
        repo = ServiceRepository(self.db)
        await repo.update(11, {"owner_show_profile": False})
        row = await repo.update(11, {"owner_user_id": 99})
        self.assertTrue(row.owner_show_profile)
        self.assertFalse(row.show_owner)

    async def test_stale_identity_map_cannot_authorize_a_reassigned_listing(self):
        stale = self.session.get(Service, 11)
        self.session.execute(update(Service).where(Service.id == 11).values(
            owner_user_id=99, name="New owner's business",
        ).execution_options(synchronize_session=False))
        self.session.commit()
        self.assertEqual(stale.owner_user_id, 40)
        with self.assertRaises(ServiceError) as caught:
            await self.service.get(40, 11)
        self.assertEqual(caught.exception.status_code, 404)
        response = await self.service.get(99, 11)
        self.assertEqual(response.name, "New owner's business")
        self.assertEqual(stale.owner_user_id, 99)

    async def test_owner_reads_hold_shared_row_lock_during_child_loading(self):
        await self.service.get(40, 11)
        await self.service.list(40, page=1, size=20)
        for statement in self.db.statements:
            sql = str(statement.compile(dialect=postgresql.dialect()))
            self.assertIn("FOR SHARE", sql)


if __name__ == "__main__":
    unittest.main()
