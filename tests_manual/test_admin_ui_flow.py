"""
End-to-end check of the exact requests Milestone 2B's admin UI issues.

Drives the running local backend (127.0.0.1:8000) with a real admin JWT and
replays the UI's call sequence: list categories, create a service, publish it,
toggle show_owner, filter the list, and confirm backend validation errors are
returned in a form the UI can display. Everything it creates is deleted at the
end, so the local database is left as it was found.
"""

import asyncio

import httpx
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api/admin/service-management"
NAME = "ZZ UI Smoke Cafe"

passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}{(' :: ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"[FAIL] {label}{(' :: ' + detail) if detail else ''}")


async def admin_token() -> str:
    async with AsyncSessionLocal() as session:
        admin = (
            await session.execute(
                select(Admin).where(Admin.is_active == True).order_by(Admin.id)  # noqa: E712
            )
        ).scalars().first()
        return create_access_token(
            {"sub": str(admin.id), "role": "admin", "super": admin.is_superadmin}, None
        )


async def cleanup(service_ids: list[int], category_ids: list[int]) -> None:
    async with AsyncSessionLocal() as session:
        for sid in service_ids:
            await session.execute(delete(ServiceContact).where(ServiceContact.service_id == sid))
            await session.execute(delete(ServiceCategory).where(ServiceCategory.service_id == sid))
            await session.execute(delete(Service).where(Service.id == sid))
        for cid in category_ids:
            await session.execute(delete(ServiceCategory).where(ServiceCategory.category_id == cid))
            await session.execute(
                Category.__table__.update()
                .where(Category.parent_id == cid)
                .values(parent_id=None)
            )
            await session.execute(delete(Category).where(Category.id == cid))
        targets = [str(x) for x in (service_ids + category_ids)]
        if targets:
            await session.execute(
                delete(AdminAuditLog).where(AdminAuditLog.target_id.in_(targets))
            )
        await session.commit()


async def main() -> None:
    token = await admin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    created_services: list[int] = []
    created_categories: list[int] = []

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # --- reads used by the UI ------------------------------------
            r = await client.get(f"{API}/categories/", headers=headers, params={"include_inactive": True})
            cats = r.json()["data"]
            check("categories list", r.status_code == 200 and len(cats) > 0, f"n={len(cats)}")
            by_slug = {c["slug"]: c for c in cats}

            r = await client.get(f"{API}/categories/tree", headers=headers, params={"include_inactive": True})
            check("category tree", r.status_code == 200 and len(r.json()["data"]) > 0)

            r = await client.get(f"{API}/services/", headers=headers, params={"page": 1, "size": 5})
            body = r.json()
            check("services list", r.status_code == 200 and "meta" in body, f"total={body['meta']['total']}")

            r = await client.get(
                f"{BASE}/api/admin/users-management/",
                headers=headers,
                params={"page": 1, "size": 3, "search": "ali"},
            )
            check("owner search", r.status_code == 200 and len(r.json()["data"]) > 0)

            # --- create (editor submit) ----------------------------------
            payload = {
                "name": NAME,
                "description": "created by 2B verification",
                "city": "Frankfurt",
                "country": "Germany",
                "persian_owned": True,
                "persian_language": True,
                "persian_service": False,
                "status": "draft",
                "source": "ui-smoke",
                "external_id": "2b-1",
                "show_owner": False,
                "contacts": [
                    {"title": "Main phone", "type": "phone", "value": "+4900000000", "display_order": 0, "is_visible": True},
                    {"title": "Reservations", "type": "phone", "value": "+4900000001", "display_order": 1, "is_visible": True},
                    {"title": "Instagram", "type": "username", "value": "ui_smoke_cafe", "platform": "instagram", "display_order": 2, "is_visible": True},
                ],
                "categories": [
                    {"category_id": by_slug["restaurant"]["id"], "is_primary": True},
                    {"category_id": by_slug["bakery"]["id"], "is_primary": False},
                ],
            }
            r = await client.post(f"{API}/services/", headers=headers, json=payload)
            check("create service", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
            svc = r.json()["data"]
            sid = svc["id"]
            created_services.append(sid)
            check("show_owner defaults false on create", svc["show_owner"] is False)
            check("three contacts incl. two same-type", len(svc["contacts"]) == 3 and sum(1 for c in svc["contacts"] if c["type"] == "phone") == 2)
            check("two categories, one primary", len(svc["categories"]) == 2 and sum(1 for c in svc["categories"] if c["is_primary"]) == 1)

            # --- publish / visibility ------------------------------------
            r = await client.patch(f"{API}/services/{sid}/status", headers=headers, json={"status": "published"})
            check("publish", r.status_code == 200 and r.json()["data"]["status"] == "published", f"status={r.status_code}")

            r = await client.patch(f"{API}/services/{sid}/show-owner", headers=headers, params={"show_owner": "true"})
            check("toggle show_owner", r.status_code == 200 and r.json()["data"]["show_owner"] is True)

            # --- list filtering -----------------------------------------
            r = await client.get(f"{API}/services/", headers=headers, params={"q": "UI Smoke", "status": "published"})
            body = r.json()
            check("filter by q+status finds it", body["meta"]["total"] >= 1 and any(s["id"] == sid for s in body["data"]))

            r = await client.get(f"{API}/services/", headers=headers, params={"category_id": by_slug["bakery"]["id"]})
            check("filter by secondary category finds it", any(s["id"] == sid for s in r.json()["data"]))

            r = await client.get(f"{API}/services/", headers=headers, params={"persian_owned": "true"})
            check("filter by persian_owned finds it", any(s["id"] == sid for s in r.json()["data"]))

            # --- owner assign -------------------------------------------
            r = await client.get(f"{BASE}/api/admin/users-management/", headers=headers, params={"page": 1, "size": 1})
            owner_id = r.json()["data"][0]["user_id"]
            r = await client.patch(f"{API}/services/{sid}/owner", headers=headers, json={"owner_user_id": owner_id})
            check("assign owner", r.status_code == 200 and r.json()["data"]["owner_user_id"] == owner_id)

            # --- validation messages the UI must show --------------------
            r = await client.post(f"{API}/services/", headers=headers, json={"name": "ZZ Dup", "source": "ui-smoke", "external_id": "2b-1"})
            check("duplicate provenance -> 409", r.status_code == 409, f"status={r.status_code}")
            check("duplicate provenance has a message", bool(r.json()["error"].get("message")), r.json()["error"].get("message", ""))

            r = await client.post(f"{API}/services/", headers=headers, json={"name": "ZZ NoCat"})
            no_cat = r.json()["data"]["id"]
            created_services.append(no_cat)
            r = await client.patch(f"{API}/services/{no_cat}/status", headers=headers, json={"status": "published"})
            check("publish without category -> 422", r.status_code == 422, f"status={r.status_code}")
            check("publish error has a message", bool(r.json()["error"].get("message")), r.json()["error"].get("message", ""))

            r = await client.patch(f"{API}/services/{sid}", headers=headers, json={"latitude": 50.1})
            check("lone latitude -> 422", r.status_code == 422, f"status={r.status_code}")

            r = await client.patch(f"{API}/services/{sid}/owner", headers=headers, json={"owner_user_id": 99999999999})
            check("unknown owner -> 404", r.status_code == 404, f"status={r.status_code}")

            r = await client.post(f"{API}/categories/", headers=headers, json={"name": "ZZ UI Root", "slug": "zz-ui-root"})
            check("create category", r.status_code == 200, f"status={r.status_code}")
            root = r.json()["data"]
            created_categories.append(root["id"])
            r = await client.patch(f"{API}/categories/{root['id']}", headers=headers, json={"is_active": False})
            check("deactivate category", r.status_code == 200 and r.json()["data"]["is_active"] is False)

            r = await client.get(f"{API}/services/")
            check("unauthenticated -> 401", r.status_code == 401, f"status={r.status_code}")
        finally:
            await cleanup(created_services, created_categories)

    print(f"\n{passed} passed, {failed} failed")
    await engine.dispose()
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
