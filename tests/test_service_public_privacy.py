"""Public discovery must not disclose private aggregate data."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession

from app.core.exceptions import register_exception_handlers
from app.models.base import Base
from app.models.category import Category, CategoryParent
from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact, ServiceContactType
from app.modules.services.public.router import (
    get_service_facets_service,
    get_service_search_service,
    public_search_rate_limit,
    router,
)
from app.modules.services.public.serialization import to_public_service
from app.modules.services.public.related_person import related_person
from app.core.exceptions import ServiceError
from app.modules.services.schemas.service_requests import (
    AdminServiceSearchParams,
    PublicServiceSearchParams,
)
from app.modules.services.search.query import ServiceQueryBuilder
from app.modules.services.search.facets_service import ServiceFacetsService, _category_tree
from app.modules.services.search.service_search_service import ServiceSearchService


def listing(*, show_owner=False):
    now = datetime.now(timezone.utc)

    def contact(visible, value):
        return ServiceContact(
            id=1 if visible else 2, title="Telephone", type=ServiceContactType.phone,
            value=value, platform=None, display_order=0, is_visible=visible,
        )

    def category(active, category_id):
        return ServiceCategory(
            category_id=category_id, is_primary=active,
            category=Category(
                id=category_id, name="Public category" if active else "Hidden category",
                slug="public" if active else "hidden", is_active=active,
            ),
        )

    return Service(
        id=7, owner_user_id=998877, show_owner=show_owner, owner_show_profile=False,
        name="Persian bakery", description="Business bio",
        persian_owned=True, persian_provider=None, persian_language=True,
        persian_service=False, address="Business address", postal_code="10115",
        city="Berlin", state="Berlin", country_code="DE", latitude=None,
        longitude=None, status=ServiceStatus.published, source="private-import",
        external_id="private-import-id", created_at=now, updated_at=now,
        contacts=[contact(True, "+493012345"), contact(False, "+499999999")],
        category_links=[category(True, 10), category(False, 11)],
    )


class PublicServicePrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_related_person_explicit_opt_out_is_still_respected(self):
        db = SimpleNamespace(execute=AsyncMock(
            return_value=SimpleNamespace(first=lambda: SimpleNamespace(
                owner_user_id=40, show_owner=True, owner_show_profile=False,
            ))
        ))
        self.assertIsNone(await related_person(db, 7))

    async def test_related_person_account_privacy_still_overrides_visible_defaults(self):
        db = SimpleNamespace(execute=AsyncMock(
            return_value=SimpleNamespace(first=lambda: SimpleNamespace(
                owner_user_id=40, show_owner=True, owner_show_profile=True,
            ))
        ))
        with patch(
            "app.modules.services.public.related_person.GetUserProfileService.execute",
            AsyncMock(side_effect=ServiceError("USER_NOT_FOUND", "Not found", 404)),
        ):
            self.assertIsNone(await related_person(db, 7))

    def app(self):
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router, prefix="/api/services")
        app.dependency_overrides[get_service_search_service] = lambda: ServiceSearchService(None)
        app.dependency_overrides[public_search_rate_limit] = lambda: None
        return app

    def test_public_projection_never_reveals_owner_or_provenance(self):
        for show_owner in (False, True):
            with self.subTest(show_owner=show_owner):
                payload = to_public_service(listing(show_owner=show_owner)).model_dump()
                for key in ("owner_user_id", "show_owner", "owner_show_profile", "source", "external_id", "status"):
                    self.assertNotIn(key, payload)
                self.assertEqual(payload["name"], "Persian bakery")
                self.assertEqual(payload["description"], "Business bio")
                self.assertIsNone(payload["persian_provider"])

    def test_hidden_contacts_and_inactive_categories_are_excluded(self):
        payload = to_public_service(listing()).model_dump()
        self.assertEqual([c["value"] for c in payload["contacts"]], ["+493012345"])
        self.assertNotIn("is_visible", payload["contacts"][0])
        self.assertEqual([c["category_id"] for c in payload["categories"]], [10])
        self.assertEqual(payload["categories"][0]["category"]["slug"], "public")

    async def test_public_and_admin_search_apply_different_read_permissions(self):
        row = listing()
        service = ServiceSearchService(db=None)
        with patch.object(ServiceQueryBuilder, "execute", AsyncMock(return_value=([row], 1))):
            public, total = await service.public_search(PublicServiceSearchParams())
            admin, admin_total = await service.admin_search(AdminServiceSearchParams())
        self.assertEqual(total, admin_total)
        self.assertNotIn("owner_user_id", public[0].model_dump())
        self.assertEqual(len(public[0].contacts), 1)
        self.assertEqual(admin[0].owner_user_id, row.owner_user_id)
        self.assertIs(admin[0].owner_show_profile, False)
        self.assertEqual(admin[0].source, row.source)
        self.assertEqual(admin[0].external_id, row.external_id)
        self.assertEqual(len(admin[0].contacts), 2)

    async def test_http_search_response_and_openapi_use_public_contract(self):
        # Exercise the route and shared query facade without a database or app
        # lifespan (which starts unrelated background workers).
        app = self.app()
        with patch.object(ServiceQueryBuilder, "execute", AsyncMock(return_value=([listing()], 1))):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/services/services/?country_code=DE")
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["data"][0]
        self.assertNotIn("owner_user_id", item)
        self.assertNotIn("source", item)
        self.assertNotIn("external_id", item)
        self.assertNotIn("+499999999", response.text)
        self.assertEqual(response.json()["meta"]["total"], 1)
        schema = app.openapi()["components"]["schemas"]["PublicServiceResponse"]
        self.assertNotIn("owner_user_id", schema["properties"])
        self.assertNotIn("source", schema["properties"])

    async def test_detail_filters_published_in_sql_and_redacts_the_response(self):
        captured = []

        async def execute(builder):
            captured.append(str(builder._stmt().compile(compile_kwargs={"literal_binds": True})))
            return [listing()], 1

        with patch.object(ServiceQueryBuilder, "execute", execute):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app()), base_url="http://test"
            ) as client:
                response = await client.get("/api/services/services/7/")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("services.status = 'published'", captured[0])
        self.assertIn("services.id = 7", captured[0])
        self.assertNotIn("owner_user_id", response.json()["data"])
        self.assertNotIn("+499999999", response.text)

    async def test_detail_missing_and_nonpublished_share_a_404(self):
        with patch.object(ServiceQueryBuilder, "execute", AsyncMock(return_value=([], 0))):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app()), base_url="http://test"
            ) as client:
                missing = await client.get("/api/services/services/999/")
                hidden = await client.get("/api/services/services/998/")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), hidden.json())
        self.assertEqual(missing.json()["error"]["code"], "SERVICE_NOT_FOUND")

    async def test_categories_static_route_and_country_validation(self):
        facets = SimpleNamespace(category_tree=AsyncMock(return_value=[]))
        app = self.app()
        app.dependency_overrides[get_service_facets_service] = lambda: facets
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/services/services/categories/?country_code=de")
            unknown = await client.get("/api/services/services/categories/?nonexistent=x")
            invalid = await client.get("/api/services/services/categories/?country_code=Germany")
        self.assertEqual(response.status_code, 200)
        facets.category_tree.assert_awaited_once_with("DE")
        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(invalid.status_code, 422)


class PublicCategoryFacetTests(unittest.IsolatedAsyncioTestCase):
    def test_legacy_category_cycle_and_its_descendants_are_omitted(self):
        rows = [
            SimpleNamespace(id=1, parent_id=2, name="Cycle one", slug="one"),
            SimpleNamespace(id=2, parent_id=1, name="Cycle two", slug="two"),
            SimpleNamespace(id=3, parent_id=1, name="Cycle child", slug="child"),
            SimpleNamespace(id=4, parent_id=None, name="Safe", slug="safe"),
        ]
        result = _category_tree(rows)
        self.assertEqual([node.id for node in result], [4])
        self.assertEqual(result[0].model_dump()["children"], [])

    async def test_query_returns_all_active_taxonomy_including_empty_and_shared_branches(self):
        # The public taxonomy is deliberately shared across countries and is
        # discoverable before a branch has any published businesses. Use real
        # ORM results/eager membership loading, not incomplete hand-written DDL.
        engine = create_engine("sqlite:///:memory:")
        try:
            Base.metadata.create_all(engine, tables=[Category.__table__, CategoryParent.__table__])
            with OrmSession(engine) as session:
                session.add_all([
                    Category(id=1, parent_id=None, name="Food", slug="food", display_order=0, is_active=True),
                    Category(id=2, parent_id=1, name="Bakery", slug="bakery", display_order=0, is_active=True),
                    Category(id=3, parent_id=None, name="Draft only", slug="draft", display_order=1, is_active=True),
                    Category(id=4, parent_id=None, name="Events", slug="events", display_order=2, is_active=True),
                    Category(id=5, parent_id=None, name="Retired", slug="retired", display_order=3, is_active=False),
                    Category(id=6, parent_id=None, name="Empty", slug="empty", display_order=4, is_active=True),
                    Category(id=7, parent_id=1, name="Retired child", slug="retired-child", display_order=1, is_active=False),
                ])
                session.flush()
                session.add_all([
                    CategoryParent(category_id=2, parent_id=1),
                    CategoryParent(category_id=2, parent_id=4),
                    CategoryParent(category_id=7, parent_id=1),
                ])
                session.commit()

                class Session:
                    async def execute(self, statement):
                        return session.execute(statement)

                service = ServiceFacetsService(Session())
                german = await service.category_tree("DE")
                international = await service.category_tree()
                french = await service.category_tree("FR")
            self.assertEqual([node.id for node in german], [1, 3, 4, 6])
            self.assertEqual([node.id for node in german[0].children], [2])
            self.assertEqual([node.id for node in german[2].children], [2])
            self.assertEqual(german[0].children[0].parent_ids, [1, 4])
            self.assertEqual(german[0].children[0].parent_id, 1)
            self.assertEqual(german[0].children[0].level, 2)
            self.assertEqual(german[3].children, [])
            self.assertEqual([node.model_dump() for node in german], [node.model_dump() for node in international])
            self.assertEqual([node.model_dump() for node in german], [node.model_dump() for node in french])
            self.assertNotIn("count", german[0].model_dump())
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
