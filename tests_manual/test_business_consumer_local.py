"""Guarded local PostgreSQL smoke test. Never imports app.main or starts workers.

Run with a working project Python: python -m tests_manual.test_business_consumer_local
Add --apply-bookmarks-migration to apply migration 17 to the guarded local DB.
Fixture writes use an outer transaction and are always rolled back.
"""

import argparse
import asyncio
from datetime import timedelta
from ipaddress import ip_address
from pathlib import Path
from uuid import uuid4

import asyncpg
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.exceptions import ServiceError
from app.models.category import Category
from app.models.service import Service, ServiceStatus
from app.models.service_bookmark import ServiceBookmark
from app.models.user import User
from app.modules.services.schemas.service_requests import (
    PublicServiceSearchParams, ServiceCreateRequest,
)
from app.modules.services.search.facets_service import ServiceFacetsService
from app.modules.services.search.service_search_service import ServiceSearchService
from app.modules.services.services.service_service import ServiceService
from app.modules.sns.owned_services.schemas import OwnedServiceUpdateRequest
from app.modules.sns.owned_services.service import OwnedServiceService
from app.modules.sns.service_bookmarks.service import ServiceBookmarkService


async def expect_error(operation, status):
    try:
        await operation
    except ServiceError as error:
        assert error.status_code == status, (error.code, error.status_code)
    else:
        raise AssertionError(f"Expected {status}")


def category_ids(nodes):
    return {
        category_id
        for node in nodes
        for category_id in ({node.id} | category_ids(node.children))
    }


async def main(apply_migration=False):
    url = make_url(settings.DATABASE_URL)
    assert (url.host, url.port, url.database) == (
        "127.0.0.1", 5433, "hoviat_service_dev"
    ), "Refusing any database except the explicitly named local development DB"
    assert settings.DISABLE_BACKGROUND_WORKERS, "Local background workers must be disabled"
    dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
    connection = await asyncpg.connect(dsn, timeout=5)
    try:
        identity = await connection.fetchrow(
            "SELECT current_database() AS db, inet_server_addr()::text AS address"
        )
        assert identity["db"] == "hoviat_service_dev"
        # Host is an exact loopback address above. A local container may report
        # its private bridge address here; a public server address is refused.
        assert ip_address(identity["address"].split("/", 1)[0]).is_private
        print(f"GUARD PASS: 127.0.0.1:5433/{identity['db']}, server {identity['address']}")
        if apply_migration:
            migration = Path(__file__).resolve().parents[1] / "scripts/database/20261016_17_add_service_bookmarks.sql"
            await connection.execute(migration.read_text(encoding="utf-8"))
            print("PASS: local additive bookmarks migration 17")
        assert await connection.fetchval("SELECT to_regclass('public.service_bookmarks')")
    finally:
        await connection.close()

    engine = create_async_engine(settings.DATABASE_URL, connect_args={"timeout": 5})
    prefix = "local-consumer-smoke-" + uuid4().hex
    fixture_ids = []
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    user_ids = list((await db.scalars(select(User.user_id).order_by(User.user_id).limit(2))).all())
                    assert len(user_ids) == 2, "Two existing local users are needed"
                    category = (await db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.parent_id.is_(None), Category.id).limit(1))).first()
                    assert category is not None, "An existing active category is needed"
                    owner, other_user = user_ids
                    domain = ServiceService(db)
                    public = ServiceSearchService(db)
                    owners = OwnedServiceService(db)
                    bookmarks = ServiceBookmarkService(db)
                    payload = dict(
                        name=prefix, description="Fixture business bio", owner_user_id=owner,
                        show_owner=False, source="local-consumer-smoke", external_id=uuid4().hex,
                        country_code="DE", state="Berlin", city="Berlin",
                        persian_language=True,
                        contacts=[
                            {"title": "Public phone", "type": "phone", "value": "+493012345", "is_visible": True},
                            {"title": "Private phone", "type": "phone", "value": "+499999999", "is_visible": False},
                        ],
                        categories=[{"category_id": category.id, "is_primary": True}],
                    )
                    published = await domain.create(ServiceCreateRequest(**payload, status="published"))
                    fixture_ids.append(published.id)
                    draft_payload = {**payload, "name": prefix + "-draft", "external_id": uuid4().hex}
                    draft = await domain.create(ServiceCreateRequest(**draft_payload, status="draft"))
                    fixture_ids.append(draft.id)

                    search, total = await public.public_search(PublicServiceSearchParams(q=prefix, country_code="DE"))
                    assert total == 1 and search[0].id == published.id
                    item = (await public.public_detail(published.id)).model_dump(mode="json")
                    assert not {"owner_user_id", "show_owner", "source", "external_id", "status"} & item.keys()
                    assert [contact["value"] for contact in item["contacts"]] == ["+493012345"]
                    await expect_error(public.public_detail(draft.id), 404)
                    assert category.id in category_ids(await ServiceFacetsService(db).category_tree("DE"))
                    if category.parent_id:
                        assert category.parent_id in category_ids(await ServiceFacetsService(db).category_tree("DE"))
                    print("PASS: published search/detail/category ancestors and public privacy")

                    await bookmarks.save(other_user, published.id)
                    await bookmarks.save(other_user, published.id)
                    assert await db.scalar(select(func.count()).select_from(ServiceBookmark).where(ServiceBookmark.bookmarker_id == other_user, ServiceBookmark.service_id == published.id)) == 1
                    saved, count = await bookmarks.list(other_user)
                    assert published.id in {row.id for row in saved}
                    assert all("owner_user_id" not in row.model_dump() for row in saved)
                    await expect_error(bookmarks.save(other_user, draft.id), 404)
                    print("PASS: private business bookmarks and duplicate saves")

                    await expect_error(owners.get(other_user, published.id), 404)
                    await expect_error(owners.update(other_user, published.id, OwnedServiceUpdateRequest(expected_updated_at=published.updated_at, description="Unauthorized")), 404)
                    before = await owners.get(owner, published.id)
                    changed = await owners.update(owner, published.id, OwnedServiceUpdateRequest(expected_updated_at=before.updated_at, description="Owner updated business bio"))
                    assert changed.description == "Owner updated business bio"
                    assert changed.status == ServiceStatus.published
                    assert len(changed.contacts) == 2
                    # now() is constant in this outer rollback transaction; an
                    # explicitly older version tests stale-write rejection.
                    await expect_error(owners.update(owner, published.id, OwnedServiceUpdateRequest(expected_updated_at=changed.updated_at - timedelta(seconds=1), description="Stale overwrite")), 409)
                    assert (await owners.get(owner, published.id)).description == "Owner updated business bio"
                    print("PASS: owner authorization, atomic edit and stale version 409")

                    await db.execute(update(Service).where(Service.id == published.id).values(status=ServiceStatus.hidden))
                    await db.commit()
                    await expect_error(public.public_detail(published.id), 404)
                    saved, _ = await bookmarks.list(other_user)
                    assert published.id not in {row.id for row in saved}
                    await bookmarks.remove(other_user, published.id)
                    await bookmarks.remove(other_user, published.id)
                    assert await db.scalar(select(func.count()).select_from(ServiceBookmark).where(ServiceBookmark.bookmarker_id == other_user, ServiceBookmark.service_id == published.id)) == 0
                    print("PASS: hidden services excluded and unbookmark idempotent")
            finally:
                await outer.rollback()
        async with engine.connect() as connection:
            remaining = await connection.scalar(select(func.count()).select_from(Service).where(Service.id.in_(fixture_ids)))
            assert remaining == 0, "Fixture rows escaped the outer rollback"
        print("PASS: all fixture services/contacts/category assignments/bookmarks rolled back")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-bookmarks-migration", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply_bookmarks_migration))
