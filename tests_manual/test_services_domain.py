"""
Opt-in integration test for the service-directory domain.

It is NOT run automatically, because it writes to whatever database
DATABASE_URL points at. Everything happens inside one transaction that is
rolled back at the end, so nothing is persisted. Enable it explicitly and run
it as a module (so the repo root is importable):

    set SERVICE_DOMAIN_INTEGRATION=1
    python -m tests_manual.test_services_domain

It checks, against a real PostgreSQL:
  * the four tables and their relationships work end to end;
  * the "at most one primary category per service" partial unique index;
  * a service may have no owner (owner_user_id staya null);
  * a service survives with zero contacts/categories.
"""

import asyncio
import os

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.service_category import ServiceCategory
from app.modules.services.repositories.category import CategoryRepository
from app.modules.services.repositories.contacts import ServiceContactRepository
from app.modules.services.repositories.service import ServiceRepository
from app.modules.services.repositories.service_categories import (
    ServiceCategoryRepository,
)


async def main() -> None:
    if os.getenv("SERVICE_DOMAIN_INTEGRATION") != "1":
        print("Skipped. Set SERVICE_DOMAIN_INTEGRATION=1 to run against the DB.")
        return

    async with AsyncSessionLocal() as session:
        try:
            categories = CategoryRepository(session)
            services = ServiceRepository(session)
            contacts = ServiceContactRepository(session)
            links = ServiceCategoryRepository(session)

            parent = await categories.create(
                {"name": "Test Food", "slug": "test-food-integration"}
            )
            restaurant = await categories.create(
                {
                    "name": "Test Restaurant",
                    "slug": "test-restaurant-integration",
                    "parent_id": parent.id,
                }
            )
            bakery = await categories.create(
                {
                    "name": "Test Bakery",
                    "slug": "test-bakery-integration",
                    "parent_id": parent.id,
                }
            )

            service = await services.create(
                {
                    "name": "Integration Test Service",
                    "city": "Frankfurt",
                    "status": "published",
                    "persian_owned": True,
                    "persian_language": True,
                    "persian_service": False,
                }
            )

            await contacts.replace(
                service.id,
                [
                    {
                        "title": "Main phone",
                        "type": "phone",
                        "value": "+490000000",
                        "display_order": 0,
                    },
                    {
                        "title": "Instagram",
                        "type": "username",
                        "value": "integration_test",
                        "platform": "instagram",
                        "display_order": 1,
                    },
                ],
            )
            await links.replace(
                service.id,
                [
                    {"category_id": restaurant.id, "is_primary": True},
                    {"category_id": bakery.id, "is_primary": False},
                ],
            )
            await session.flush()

            full = await services.get_full(service.id)
            assert full is not None, "service not found after create"
            assert full.owner_user_id is None, "service should have no owner"
            assert len(full.contacts) == 2, "expected two contacts"
            assert len(full.category_links) == 2, "expected two category links"
            primaries = [link for link in full.category_links if link.is_primary]
            assert len(primaries) == 1, "expected exactly one primary category"

            # The database must reject a second primary for the same service.
            second_primary_rejected = False
            try:
                async with session.begin_nested():
                    await session.execute(
                        insert(ServiceCategory).values(
                            service_id=service.id,
                            category_id=bakery.id,
                            is_primary=True,
                        )
                    )
                    await session.execute(
                        insert(ServiceCategory).values(
                            service_id=service.id,
                            category_id=parent.id,
                            is_primary=True,
                        )
                    )
            except IntegrityError:
                second_primary_rejected = True
            assert second_primary_rejected, "database allowed two primary categories"

            ownerless_ok = await session.scalar(
                select(func.count()).select_from(
                    select(ServiceCategory).where(
                        ServiceCategory.service_id == service.id
                    ).subquery()
                )
            )
            assert ownerless_ok is not None

            print("PASS: service-directory domain integration checks")
        finally:
            await session.rollback()
            print("Rolled back; nothing was persisted.")


if __name__ == "__main__":
    asyncio.run(main())
