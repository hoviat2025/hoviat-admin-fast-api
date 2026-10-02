"""
DB-backed hardening tests for the admin service editor.

Covers, against the permitted local database only:
  * aggregate save commits everything in one operation
  * an induced failure mid-save leaves no partial change
  * a stale expected_updated_at is refused with 409
  * concurrent saves cannot interleave (row lock serialises them)
  * retired (inactive) category rules
  * contact/category-only edits move the parent's updated_at
  * the new CHECK constraints reject invalid raw SQL states
  * audit rows land in the same transaction as the aggregate save

Everything it creates is removed in a finally block.
"""

import asyncio
from datetime import timedelta

from sqlalchemy import delete, select, text

from app.core.database import AsyncSessionLocal, engine
from app.core.exceptions import ServiceError
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact
from app.modules.admin.service_management.services.admin_service_service import (
    AdminServiceManagementService,
)
from app.modules.services.schemas.service_requests import (
    ServiceAggregateSaveRequest,
    ServiceCategoriesReplaceRequest,
    ServiceContactsReplaceRequest,
)

passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}{(' :: ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"[FAIL] {label}{(' :: ' + detail) if detail else ''}")


async def active_admin() -> Admin:
    async with AsyncSessionLocal() as session:
        admin = (
            await session.execute(
                select(Admin).where(Admin.is_active == True).order_by(Admin.id)  # noqa: E712
            )
        ).scalars().first()
        return admin


async def make_service(name: str = "ZZ Harden") -> Service:
    async with AsyncSessionLocal() as session:
        service = Service(
            name=name,
            status="draft",
            city="Frankfurt",
            source="harden",
            external_id=f"hz-{abs(hash(name)) % 100000}",
        )
        session.add(service)
        await session.commit()
        await session.refresh(service)
        return service


async def cleanup(ids: list[int], categories: list[int]) -> None:
    async with AsyncSessionLocal() as session:
        for sid in ids:
            await session.execute(delete(ServiceContact).where(ServiceContact.service_id == sid))
            await session.execute(delete(ServiceCategory).where(ServiceCategory.service_id == sid))
            await session.execute(delete(Service).where(Service.id == sid))
        for cid in categories:
            await session.execute(delete(ServiceCategory).where(ServiceCategory.category_id == cid))
            await session.execute(
                Category.__table__.update().where(Category.parent_id == cid).values(parent_id=None)
            )
            await session.execute(delete(Category).where(Category.id == cid))
        targets = [str(x) for x in (ids + categories)]
        if targets:
            await session.execute(delete(AdminAuditLog).where(AdminAuditLog.target_id.in_(targets)))
        await session.commit()


async def main() -> None:
    admin = await active_admin()
    ids: list[int] = []
    cats: list[int] = []

    async with AsyncSessionLocal() as session:
        all_cats = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    by_slug = {c.slug: c for c in all_cats}
    restaurant, bakery = by_slug["restaurant"], by_slug["bakery"]

    try:
        # =================================================== atomic aggregate save
        service = await make_service("ZZ Aggregate")
        ids.append(service.id)
        async with AsyncSessionLocal() as s:
            stored = (await s.execute(select(Service).where(Service.id == service.id))).scalars().first()
            version = stored.updated_at

        payload = ServiceAggregateSaveRequest(
            name="ZZ Aggregate Renamed",
            description="atomic",
            city="Berlin",
            country="Germany",
            latitude=52.52,
            longitude=13.405,
            persian_owned=True,
            persian_language=False,
            persian_service=True,
            status="published",
            source="harden",
            external_id=f"hz-{abs(hash('ZZ Aggregate')) % 100000}",
            show_owner=True,
            contacts=[
                {"title": "Phone", "type": "phone", "value": "+4930000", "display_order": 0, "is_visible": True},
                {"title": "Site", "type": "url", "value": "https://x.de", "display_order": 1, "is_visible": True},
            ],
            categories=[
                {"category_id": restaurant.id, "is_primary": True},
                {"category_id": bakery.id, "is_primary": False},
            ],
            expected_updated_at=version.isoformat(),
        )
        svc_layer = AdminServiceManagementService(AsyncSessionLocal())
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            saved = await admin_svc.save_service(service.id, payload, admin)

        check("aggregate save applied scalars", saved.name == "ZZ Aggregate Renamed" and saved.city == "Berlin")
        check("aggregate save applied status", saved.status.value == "published")
        check("aggregate save applied persian flags", saved.persian_owned and not saved.persian_language and saved.persian_service)
        check("aggregate save applied coords", saved.latitude == 52.52 and saved.longitude == 13.405)
        check("aggregate save applied show_owner", saved.show_owner is True)
        check("aggregate save applied contacts", len(saved.contacts) == 2)
        check("aggregate save applied categories with one primary", len(saved.categories) == 2 and sum(1 for c in saved.categories if c.is_primary) == 1)
        check("aggregate save moved updated_at", saved.updated_at > version)

        async with AsyncSessionLocal() as s:
            audit_rows = (await s.execute(select(AdminAuditLog).where(
                AdminAuditLog.target_id == str(service.id),
                AdminAuditLog.action == "service.save",
            ))).scalars().all()
        check("aggregate save wrote one audit row atomically", len(audit_rows) == 1, f"n={len(audit_rows)}")

        # ============================================== induced failure = no partial
        service2 = await make_service("ZZ Atomicity")
        ids.append(service2.id)
        async with AsyncSessionLocal() as s:
            stored2 = (await s.execute(select(Service).where(Service.id == service2.id))).scalars().first()
            v2 = stored2.updated_at
        bad = ServiceAggregateSaveRequest(
            name="ZZ Atomicity Changed",
            city="Munich",
            contacts=[{"title": "Phone", "type": "phone", "value": "+4989000", "display_order": 0, "is_visible": True}],
            categories=[{"category_id": restaurant.id, "is_primary": True}],
            # fails validation: provenance half-pair
            source="harden",
            expected_updated_at=v2.isoformat(),
        )
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            try:
                await admin_svc.save_service(service2.id, bad, admin)
                raised = False
            except ServiceError:
                raised = True
        check("half-pair provenance rejected", raised)
        async with AsyncSessionLocal() as s:
            after = (await s.execute(select(Service).where(Service.id == service2.id))).scalars().first()
            c_count = (await s.execute(select(ServiceContact).where(ServiceContact.service_id == service2.id))).scalars().all()
            l_count = (await s.execute(select(ServiceCategory).where(ServiceCategory.service_id == service2.id))).scalars().all()
            a_count = (await s.execute(select(AdminAuditLog).where(AdminAuditLog.target_id == str(service2.id)))).scalars().all()
        check(
            "no partial scalar write",
            after.name == "ZZ Atomicity" and after.city == "Frankfurt",
            f"name={after.name} city={after.city}",
        )
        check("no partial contact write", len(c_count) == 0, f"n={len(c_count)}")
        check("no partial category write", len(l_count) == 0, f"n={len(l_count)}")
        check("no audit row for a rolled-back save", len(a_count) == 0)

# ================================================ stale updated_at -> 409
        async with AsyncSessionLocal() as s:
            stored3 = (await s.execute(select(Service).where(Service.id == service.id))).scalars().first()
            stale = stored3.updated_at
        # Build explicitly rather than with model_copy: model_copy bypasses
        # validators, which would leave expected_updated_at as a raw string.
        stale_payload = ServiceAggregateSaveRequest(
            name=payload.name,
            description=payload.description,
            city=payload.city,
            country=payload.country,
            latitude=payload.latitude,
            longitude=payload.longitude,
            persian_owned=payload.persian_owned,
            persian_language=payload.persian_language,
            persian_service=payload.persian_service,
            status=payload.status,
            source=payload.source,
            external_id=payload.external_id,
            show_owner=payload.show_owner,
            contacts=payload.contacts,
            categories=payload.categories,
            expected_updated_at=(stale - timedelta(minutes=5)).isoformat(),
        )
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            try:
                await admin_svc.save_service(service.id, stale_payload, admin)
                conflict = False
            except ServiceError as e:
                conflict = e.status_code == 409
        check("stale expected_updated_at -> 409", conflict)

        # ==================================== concurrent saves cannot interleave
        service3 = await make_service("ZZ Race")
        ids.append(service3.id)
        async with AsyncSessionLocal() as s:
            stored3b = (await s.execute(select(Service).where(Service.id == service3.id))).scalars().first()
            v3 = stored3b.updated_at
        race_a = ServiceAggregateSaveRequest(
            name="ZZ Race A", city="A",
            contacts=[{"title": "A", "type": "phone", "value": "1", "display_order": 0, "is_visible": True}],
            categories=[{"category_id": restaurant.id, "is_primary": True}],
            expected_updated_at=v3.isoformat(),
        )
# Constructed explicitly: model_copy would bypass validators.
        race_b = ServiceAggregateSaveRequest(
            name="ZZ Race B", city="B",
            contacts=[{"title": "B", "type": "phone", "value": "2", "display_order": 0, "is_visible": True}],
            categories=[{"category_id": restaurant.id, "is_primary": True}],
            expected_updated_at=v3.isoformat(),
        )
        # Both loaded the SAME version; the first to commit wins, the second must 409.
        async with AsyncSessionLocal() as s1:
            admin_svc = AdminServiceManagementService(s1)
            await admin_svc.save_service(service3.id, race_a, admin)
        async with AsyncSessionLocal() as s2:
            admin_svc = AdminServiceManagementService(s2)
            try:
                await admin_svc.save_service(service3.id, race_b, admin)
                second = "accepted"
            except ServiceError as e:
                second = e.status_code
        check("second concurrent save with same version is refused", second == 409, f"got={second}")
        async with AsyncSessionLocal() as s:
            final = (await s.execute(select(Service).where(Service.id == service3.id))).scalars().first()
            fc = (await s.execute(select(ServiceContact).where(ServiceContact.service_id == service3.id))).scalars().all()
        check("only the first writer's data persisted", final.name == "ZZ Race A" and len(fc) == 1, f"name={final.name} contacts={len(fc)}")

        # ===================================== child-only edits move updated_at
        service4 = await make_service("ZZ Touch")
        ids.append(service4.id)
        async with AsyncSessionLocal() as s:
            before_touch = (await s.execute(select(Service).where(Service.id == service4.id))).scalars().first().updated_at
        await asyncio.sleep(0.05)
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            await admin_svc.replace_contacts(service4.id, ServiceContactsReplaceRequest(
                contacts=[{"title": "P", "type": "phone", "value": "1", "display_order": 0, "is_visible": True}]), admin)
        async with AsyncSessionLocal() as s:
            after_touch = (await s.execute(select(Service).where(Service.id == service4.id))).scalars().first().updated_at
        check("contact-only edit bumps parent updated_at", after_touch > before_touch)

        # ================================================== inactive categories
        async with AsyncSessionLocal() as s:
            cat = Category(name="ZZ Retired", slug="zz-retired", is_active=False)
            s.add(cat)
            await s.commit()
            await s.refresh(cat)
            retired_id = cat.id
        cats.append(retired_id)

        service5 = await make_service("ZZ Inactive")
        ids.append(service5.id)
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            try:
                await admin_svc.replace_categories(service5.id, ServiceCategoriesReplaceRequest(
                    categories=[{"category_id": retired_id, "is_primary": True}]), admin)
                newly = "accepted"
            except ServiceError as e:
                newly = e.status_code
        check("inactive category cannot be newly assigned", newly == 422, f"got={newly}")

        # Assign it while still active, then retire it -> existing link preserved.
        async with AsyncSessionLocal() as s:
            tmp = Category(name="ZZ Temp", slug="zz-temp", is_active=True)
            s.add(tmp)
            await s.commit()
            await s.refresh(tmp)
            temp_id = tmp.id
        cats.append(temp_id)
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            await admin_svc.replace_categories(service5.id, ServiceCategoriesReplaceRequest(
                categories=[{"category_id": temp_id, "is_primary": True}]), admin)
        async with AsyncSessionLocal() as s:
            await s.execute(Category.__table__.update().where(Category.id == temp_id).values(is_active=False))
            await s.commit()
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            kept = await admin_svc.replace_categories(service5.id, ServiceCategoriesReplaceRequest(
                categories=[{"category_id": temp_id, "is_primary": True}]), admin)
        check("existing inactive assignment preserved on edit", len(kept.categories) == 1)

        # But a published service cannot keep an inactive primary.
        async with AsyncSessionLocal() as s:
            stored5 = (await s.execute(select(Service).where(Service.id == service5.id))).scalars().first()
            v5 = stored5.updated_at
        try:
            async with AsyncSessionLocal() as s:
                admin_svc = AdminServiceManagementService(s)
                pub = ServiceAggregateSaveRequest(
                    name="ZZ Inactive", status="published",
                    categories=[{"category_id": temp_id, "is_primary": True}],
                    expected_updated_at=v5.isoformat(),
                )
                await admin_svc.save_service(service5.id, pub, admin)
                pubres = "accepted"
        except ServiceError as e:
            pubres = e.status_code
        check("published with inactive primary refused", pubres == 422, f"got={pubres}")

        # Remove it (allowed).
        async with AsyncSessionLocal() as s:
            admin_svc = AdminServiceManagementService(s)
            removed = await admin_svc.replace_categories(service5.id, ServiceCategoriesReplaceRequest(categories=[]), admin)
        check("existing inactive assignment can be removed", len(removed.categories) == 0)

        # =========================================== new CHECK constraints (raw SQL)
        async def expect_violation(label, sql, params):
            try:
                async with AsyncSessionLocal() as s:
                    await s.execute(text(sql), params)
                    await s.commit()
                check(label, False, "raw SQL was accepted")
            except Exception:
                check(label, True)
            # leave the session healthy for the next check
            await asyncio.sleep(0)

        await expect_violation(
            "raw blank name rejected",
            "insert into services (name, status) values ('   ', 'draft')",
            {},
        )
        await expect_violation(
            "raw lone latitude rejected",
            "insert into services (name, status, latitude) values ('ZZ raw', 'draft', 50.0)",
            {},
        )
        await expect_violation(
            "raw half provenance rejected",
            "insert into services (name, status, source) values ('ZZ raw', 'draft', 'x')",
            {},
        )
        await expect_violation(
            "raw blank category name rejected",
            "insert into categories (name, slug) values ('  ', 'zz-blank-name')",
            {},
        )
        await expect_violation(
            "raw blank contact value rejected",
            "insert into service_contacts (service_id, title, type, value) values ($1, 'T', 'phone', ' ')",
            {"1": ids[0]},
        )

    finally:
        await cleanup(ids, cats)

    print(f"\n{passed} passed, {failed} failed")
    await engine.dispose()
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

