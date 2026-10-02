"""
DB-backed admin API test for the service-management endpoints (Milestone 2A).

Runs against the permitted local database only (127.0.0.1:5433 / hoviat_service_dev).
It drives the real FastAPI app through the real admin auth dependency by minting
a JWT with the app's own create_access_token for an existing local admin.

Everything it creates is deleted in a finally block, so the restored production
copy is left as it was found. Run with:

    set PYTHONIOENCODING=utf-8
    python -m tests_manual.test_admin_service_api
"""

import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact
from app.models.user import User
from app.main import app

PREFIX = "/api/admin/service-management"


async def _admin_token() -> tuple[str, int]:
    """A valid admin JWT for an existing active admin in the local DB."""
    async with AsyncSessionLocal() as session:
        admin = (
            await session.execute(
                select(Admin).where(
                    Admin.is_active == True  # noqa: E712
                ).order_by(Admin.id)
            )
        ).scalars().first()
        if admin is None:
            raise RuntimeError("no active admin in the local database")
        token = create_access_token(
            data={"sub": str(admin.id), "role": "admin", "super": admin.is_superadmin},
            expires_delta=None,
        )
        return token, admin.id


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}{(' :: ' + detail) if detail else ''}")
    if not condition:
        raise AssertionError(label)


async def main() -> None:
    token, admin_id = await _admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    created_service_ids: list[int] = []
    created_category_ids: list[int] = []

    # Remove any artefacts left behind by an interrupted earlier run, so the
    # script is safe to re-run.
    async with AsyncSessionLocal() as session:
        stale = (
            await session.execute(select(Service).where(Service.name.like("ZZ %")))
        ).scalars().all()
        for row in stale:
            await session.execute(
                delete(ServiceContact).where(ServiceContact.service_id == row.id)
            )
            await session.execute(
                delete(ServiceCategory).where(ServiceCategory.service_id == row.id)
            )
            await session.execute(delete(Service).where(Service.id == row.id))
        stale_cats = (
            await session.execute(
                select(Category).where(Category.slug.like("zz-%"))
            )
        ).scalars().all()
        for row in stale_cats:
            await session.execute(
                delete(ServiceCategory).where(ServiceCategory.category_id == row.id)
            )
        # Detach children before deleting parents: categories.parent_id is
        # ON DELETE RESTRICT by design.
        await session.execute(
            Category.__table__.update()
            .where(Category.parent_id.is_not(None))
            .values(parent_id=None)
        )
        for row in stale_cats:
            await session.execute(delete(Category).where(Category.id == row.id))
        await session.commit()
        if stale or stale_cats:
            print(
                f"pre-clean: removed {len(stale)} stale service(s), "
                f"{len(stale_cats)} stale categor(y/ies) from a previous run"
            )

    try:
        await _run(headers, admin_id, created_service_ids, created_category_ids)
    finally:
        async with AsyncSessionLocal() as session:
            for service_id in created_service_ids:
                await session.execute(
                    delete(ServiceContact).where(ServiceContact.service_id == service_id)
                )
                await session.execute(
                    delete(ServiceCategory).where(ServiceCategory.service_id == service_id)
                )
                await session.execute(delete(Service).where(Service.id == service_id))
            for category_id in created_category_ids:
                await session.execute(
                    delete(ServiceCategory).where(ServiceCategory.category_id == category_id)
                )
            # Detach before delete (categories.parent_id is ON DELETE RESTRICT).
            for category_id in created_category_ids:
                await session.execute(
                    Category.__table__.update()
                    .where(Category.parent_id == category_id)
                    .values(parent_id=None)
                )
            for category_id in created_category_ids:
                await session.execute(delete(Category).where(Category.id == category_id))

            # Remove the audit rows this run produced, so the restored local
            # database is left exactly as it was found.
            targets = [str(x) for x in (created_service_ids + created_category_ids)]
            if targets:
                await session.execute(
                    delete(AdminAuditLog).where(AdminAuditLog.target_id.in_(targets))
                )
            await session.commit()
            print(
                "cleanup: removed",
                len(created_service_ids),
                "service(s),",
                len(created_category_ids),
                "category/categories, and their audit rows",
            )
        await engine.dispose()
    print("PASS: admin service-management API checks")


async def _run(
    headers: dict,
    admin_id: int,
    created_service_ids: list[int],
    created_category_ids: list[int],
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://local") as client:
        # ---------------------------------------------------------- auth guard
        r = await client.get(f"{PREFIX}/services/")
        check(
            "unauthenticated list is rejected",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        # ------------------------------------------------------------ categories
        r = await client.get(f"{PREFIX}/categories/", headers=headers)
        check(
            "list categories",
            r.status_code == 200 and isinstance(r.json()["data"], list),
            f"status={r.status_code} count={len(r.json().get('data', []))}",
        )
        seeded = {c["slug"]: c["id"] for c in r.json()["data"]}
        check("seeded categories present", "restaurant" in seeded, f"found={len(seeded)}")

        r = await client.get(f"{PREFIX}/categories/tree", headers=headers)
        check(
            "category tree",
            r.status_code == 200 and len(r.json()["data"]) > 0,
            f"roots={len(r.json().get('data', []))}",
        )

        # Create a dedicated parent + child so cleanup is precise.
        r = await client.post(
            f"{PREFIX}/categories/",
            headers=headers,
            json={"name": "ZZ Test Root", "slug": "zz-test-root"},
        )
        check("create category", r.status_code == 200, f"status={r.status_code}")
        root = r.json()["data"]
        created_category_ids.append(root["id"])

        r = await client.post(
            f"{PREFIX}/categories/",
            headers=headers,
            json={"name": "ZZ Test Child", "slug": "zz-test-child", "parent_id": root["id"]},
        )
        check("create child category", r.status_code == 200, f"status={r.status_code}")
        child = r.json()["data"]
        created_category_ids.append(child["id"])

        # Duplicate slug is a conflict.
        r = await client.post(
            f"{PREFIX}/categories/",
            headers=headers,
            json={"name": "Dup", "slug": "zz-test-root"},
        )
        check("duplicate category slug rejected", r.status_code == 409, f"status={r.status_code}")

        # Cycle guard: move the root under its own child.
        r = await client.patch(
            f"{PREFIX}/categories/{root['id']}",
            headers=headers,
            json={"parent_id": child["id"]},
        )
        check("category cycle rejected", r.status_code in (400, 422), f"status={r.status_code}")

        # Deactivate.
        r = await client.patch(
            f"{PREFIX}/categories/{child['id']}",
            headers=headers,
            json={"is_active": False},
        )
        check(
            "deactivate category",
            r.status_code == 200 and r.json()["data"]["is_active"] is False,
            f"status={r.status_code}",
        )

        # A retired category must not be newly assignable (approved rule), so
        # create a separate still-active category for the assignment flow.
        r = await client.post(
            f"{PREFIX}/categories/",
            headers=headers,
            json={"name": "ZZ Test Active", "slug": "zz-test-active", "parent_id": root["id"]},
        )
        check("create active category", r.status_code == 200, f"status={r.status_code}")
        active_cat = r.json()["data"]
        created_category_ids.append(active_cat["id"])

        # ------------------------------------------------------------- services
        r = await client.post(
            f"{PREFIX}/services/",
            headers=headers,
            json={
                "name": "ZZ Test Service",
                "description": "integration",
                "city": "Frankfurt",
                "persian_owned": True,
                "persian_language": True,
                "status": "draft",
            },
        )
        check("create service", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        svc = r.json()["data"]
        sid = svc["id"]
        created_service_ids.append(sid)
        check(
            "show_owner defaults to false",
            svc["show_owner"] is False,
            f"show_owner={svc['show_owner']}",
        )
        check("owner defaults to null", svc["owner_user_id"] is None)

        # Publish without a category must be refused (approved rule).
        r = await client.patch(
            f"{PREFIX}/services/{sid}/status", headers=headers, json={"status": "published"}
        )
        check(
            "publish without category refused",
            r.status_code in (400, 422),
            f"status={r.status_code}",
        )

        # A retired category cannot be newly assigned.
        r = await client.put(
            f"{PREFIX}/services/{sid}/categories",
            headers=headers,
            json={"categories": [{"category_id": child["id"], "is_primary": True}]},
        )
        check(
            "assign retired category refused",
            r.status_code in (400, 422),
            f"status={r.status_code} body={r.text[:200]}",
        )

        # Assign two active categories with one primary.
        r = await client.put(
            f"{PREFIX}/services/{sid}/categories",
            headers=headers,
            json={
                "categories": [
                    {"category_id": active_cat["id"], "is_primary": True},
                    {"category_id": seeded["bakery"], "is_primary": False},
                ]
            },
        )
        check("assign categories", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        cats = r.json()["data"]["categories"]
        check("two categories assigned", len(cats) == 2, f"n={len(cats)}")
        check("exactly one primary", sum(1 for c in cats if c["is_primary"]) == 1)

        # Two primaries must be refused.
        r = await client.put(
            f"{PREFIX}/services/{sid}/categories",
            headers=headers,
            json={
                "categories": [
                    {"category_id": active_cat["id"], "is_primary": True},
                    {"category_id": seeded["bakery"], "is_primary": True},
                ]
            },
        )
        check("two primaries refused", r.status_code in (400, 422), f"status={r.status_code}")

        # Now publish (one primary present).
        r = await client.patch(
            f"{PREFIX}/services/{sid}/status", headers=headers, json={"status": "published"}
        )
        check("publish with primary", r.status_code == 200 and r.json()["data"]["status"] == "published", f"status={r.status_code}")

        # Contacts.
        r = await client.put(
            f"{PREFIX}/services/{sid}/contacts",
            headers=headers,
            json={
                "contacts": [
                    {"title": "Main phone", "type": "phone", "value": "+490000000", "display_order": 0},
                    {"title": "Reservations", "type": "phone", "value": "+490000001", "display_order": 1},
                    {"title": "Instagram", "type": "username", "value": "zz_test", "platform": "instagram", "display_order": 2},
                ]
            },
        )
        check("replace contacts", r.status_code == 200, f"status={r.status_code}")
        check("three contacts", len(r.json()["data"]["contacts"]) == 3)
        check(
            "two same-type contacts allowed",
            sum(1 for c in r.json()["data"]["contacts"] if c["type"] == "phone") == 2,
        )

        # Coordinates must be a pair.
        r = await client.patch(
            f"{PREFIX}/services/{sid}", headers=headers, json={"latitude": 50.1}
        )
        check("lone latitude refused", r.status_code in (400, 422), f"status={r.status_code}")

        # Provenance set + uniqueness.
        r = await client.patch(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"source": "atlas", "external_id": "zz-1"},
        )
        check(
            "set provenance",
            r.status_code == 200 and r.json()["data"]["external_id"] == "zz-1",
            f"status={r.status_code}",
        )

        r = await client.post(
            f"{PREFIX}/services/",
            headers=headers,
            json={"name": "ZZ Dup Source", "source": "atlas", "external_id": "zz-1"},
        )
        check("duplicate provenance refused", r.status_code == 409, f"status={r.status_code}")

        # Correcting only `source` while `external_id` already exists keeps a
        # complete pair, so it is allowed and the pair becomes ("manual","zz-1").
        r = await client.patch(
            f"{PREFIX}/services/{sid}", headers=headers, json={"source": "manual"}
        )
        check(
            "source-only correction allowed (pair stays complete)",
            r.status_code == 200
            and r.json()["data"]["source"] == "manual"
            and r.json()["data"]["external_id"] == "zz-1",
            f"status={r.status_code}",
        )

        r = await client.patch(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"source": None, "external_id": None},
        )
        check(
            "clear provenance",
            r.status_code == 200
            and r.json()["data"]["source"] is None
            and r.json()["data"]["external_id"] is None,
            f"status={r.status_code}",
        )

        # Setting exactly one field on a service with NO provenance is the
        # genuinely invalid half-pair and must be refused.
        r = await client.post(
            f"{PREFIX}/services/", headers=headers, json={"name": "ZZ Half Pair"}
        )
        half = r.json()["data"]
        created_service_ids.append(half["id"])
        r = await client.patch(
            f"{PREFIX}/services/{half['id']}", headers=headers, json={"source": "atlas"}
        )
        check(
            "half provenance pair refused",
            r.status_code in (400, 422),
            f"status={r.status_code}",
        )

        # show_owner toggle.
        r = await client.patch(
            f"{PREFIX}/services/{sid}/show-owner", headers=headers, params={"show_owner": True}
        )
        check("show_owner true", r.status_code == 200 and r.json()["data"]["show_owner"] is True, f"status={r.status_code}")

        # Owner assignment to a real user from the restored data.
        async with AsyncSessionLocal() as session:
            owner_id = await session.scalar(select(User.user_id).limit(1))
        r = await client.patch(
            f"{PREFIX}/services/{sid}/owner", headers=headers, json={"owner_user_id": owner_id}
        )
        check("assign owner", r.status_code == 200 and r.json()["data"]["owner_user_id"] == owner_id, f"status={r.status_code}")

        # Unknown owner must be refused.
        r = await client.patch(
            f"{PREFIX}/services/{sid}/owner", headers=headers, json={"owner_user_id": 99999999999}
        )
        check("unknown owner refused", r.status_code == 404, f"status={r.status_code}")

        # Clear owner.
        r = await client.patch(
            f"{PREFIX}/services/{sid}/owner", headers=headers, json={"owner_user_id": None}
        )
        check("clear owner", r.status_code == 200 and r.json()["data"]["owner_user_id"] is None, f"status={r.status_code}")

        # ---------------------------------------------------------------- list
        r = await client.get(f"{PREFIX}/services/", headers=headers, params={"q": "ZZ Test", "status": "published"})
        check("admin search by q+status", r.status_code == 200, f"status={r.status_code}")
        body = r.json()
        check("search found the service", any(s["id"] == sid for s in body["data"]), f"total={body['meta']['total']}")
        check("meta has pagination", set(["total", "page", "size", "pages"]).issubset(body["meta"].keys()))

        r = await client.get(f"{PREFIX}/services/", headers=headers, params={"category_id": active_cat["id"]})
        check("search by category", r.status_code == 200 and r.json()["meta"]["total"] >= 1, f"total={r.json()['meta']['total']}")

        # ----------------------------------------------------------- audit rows
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(AdminAuditLog).where(AdminAuditLog.target_id == str(sid))
                )
            ).scalars().all()
            actions = sorted({row.action for row in rows})
        expected = {
            "service.create",
            "service.status_change",
            "service.categories_change",
            "service.contacts_change",
            "service.update",
            "service.show_owner_change",
            "service.owner_change",
        }
        check(
            "audit rows recorded for the service",
            expected.issubset(set(actions)),
            f"actions={actions}",
        )
        check("audit rows attributed to the admin", all(r.admin_id == admin_id for r in rows))

        async with AsyncSessionLocal() as session:
            cat_rows = (
                await session.execute(
                    select(AdminAuditLog).where(AdminAuditLog.target_id == str(child["id"]))
                )
            ).scalars().all()
        check(
            "category audit recorded",
            any(row.action.startswith("category.") for row in cat_rows),
            f"actions={[row.action for row in cat_rows]}",
        )


if __name__ == "__main__":
    asyncio.run(main())
