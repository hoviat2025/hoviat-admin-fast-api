"""End-to-end checks for the atomic service aggregate save endpoint.

Exercises the real HTTP surface the admin editor uses:

    PUT /api/admin/service-management/services/{id}

via the ASGI app, against the local development database. Verifies that one
request commits scalars, owner, show_owner, contacts, categories and the audit
row together; that a stale ``expected_updated_at`` is refused with 409; and that
a refused save leaves no partial writes behind.

Run:  venv\\Scripts\\python.exe -m tests_manual.test_service_aggregate_api
"""

import asyncio
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.main import app
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact

PREFIX = "/api/admin/service-management"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"[PASS] {label}" + (f" :: {detail}" if detail else ""))
    else:
        failures.append(label)
        print(f"[FAIL] {label}" + (f" :: {detail}" if detail else ""))


async def _admin_token() -> tuple[str, int]:
    async with AsyncSessionLocal() as session:
        admin = (
            await session.execute(
                select(Admin).where(Admin.is_active == True).order_by(Admin.id)  # noqa: E712
            )
        ).scalars().first()
        if admin is None:
            raise RuntimeError("no active admin in the local database")
        return (
            create_access_token(
                data={"sub": str(admin.id), "role": "admin", "super": admin.is_superadmin},
                expires_delta=None,
            ),
            admin.id,
        )


async def _new_category(client: AsyncClient, headers: dict, slug: str) -> dict:
    r = await client.post(
        f"{PREFIX}/categories/",
        headers=headers,
        json={"name": f"ZZ Agg {slug}", "slug": slug, "parent_id": None},
    )
    check(f"create category {slug}", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    return r.json()["data"]


async def _new_service(client: AsyncClient, headers: dict) -> dict:
    r = await client.post(
        f"{PREFIX}/services/",
        headers=headers,
        json={"name": "ZZ Aggregate Service", "status": ServiceStatus.draft.value},
    )
    check("create service", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    return r.json()["data"]


def _aggregate(name: str, token: str, **over: Any) -> dict:
    body: dict[str, Any] = {
        "name": name,
        "description": "aggregate e2e",
        "city": "Berlin",
        "country_code": "DE",
        "persian_owned": True,
        "persian_provider": None,
        "persian_language": False,
        "persian_service": False,
        "status": ServiceStatus.draft.value,
        "show_owner": False,
        "owner_user_id": None,
        "contacts": [
            {"title": "Phone", "type": "phone", "value": "+49 30 1", "display_order": 0, "is_visible": True}
        ],
        "categories": [],
        "expected_updated_at": token,
    }
    body.update(over)
    return body


async def _audit_count(service_id: int) -> int:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AdminAuditLog).where(AdminAuditLog.target_id == str(service_id))
            )
        ).scalars().all()
    return len(rows)


async def _run(headers: dict, admin_id: int, created: dict) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://local") as client:
        primary = await _new_category(client, headers, "zz-agg-primary")
        secondary = await _new_category(client, headers, "zz-agg-secondary")
        svc = await _new_service(client, headers)
        sid = svc["id"]
        created["services"].append(sid)
        created["categories"] += [primary["id"], secondary["id"]]

        # Baseline already includes the audit row written by the create call.
        baseline = await _audit_count(sid)
        check("create wrote one audit row", baseline == 1, f"n={baseline}")

        # ------------------------------------------------- one-request save
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json=_aggregate(
                "ZZ Aggregate Saved",
                svc["updated_at"],
                categories=[
                    {"category_id": primary["id"], "is_primary": True},
                    {"category_id": secondary["id"], "is_primary": False},
                ],
                status=ServiceStatus.published.value,
            ),
        )
        check("aggregate PUT accepted", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        body = r.json()["data"]

        async with AsyncSessionLocal() as session:
            stored = (
                await session.execute(select(Service).where(Service.id == sid))
            ).scalars().first()
            contacts = (
                await session.execute(select(ServiceContact).where(ServiceContact.service_id == sid))
            ).scalars().all()
            links = (
                await session.execute(select(ServiceCategory).where(ServiceCategory.service_id == sid))
            ).scalars().all()
            audit = (
                await session.execute(
                    select(AdminAuditLog).where(AdminAuditLog.target_id == str(sid))
                )
            ).scalars().all()

        check("scalars committed", stored.name == "ZZ Aggregate Saved", f"name={stored.name}")
        check("status committed", stored.status == ServiceStatus.published.value, f"status={stored.status}")
        check("contacts committed", len(contacts) == 1, f"n={len(contacts)}")
        check("categories committed", len(links) == 2, f"n={len(links)}")
        check("exactly one primary", sum(1 for link in links if link.is_primary) == 1)
        check(
            "the save added exactly one audit row",
            len(audit) == baseline + 1,
            f"n={len(audit)} baseline={baseline}",
        )
        check("audit attributed to admin", all(row.admin_id == admin_id for row in audit))

        # ------------------------------------------- stale token -> 409
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json=_aggregate("ZZ Should Not Apply", svc["updated_at"]),
        )
        check("stale expected_updated_at -> 409", r.status_code == 409, f"status={r.status_code}")

        async with AsyncSessionLocal() as session:
            unchanged = (
                await session.execute(select(Service).where(Service.id == sid))
            ).scalars().first()
            stale_audit = (
                await session.execute(
                    select(AdminAuditLog).where(AdminAuditLog.target_id == str(sid))
                )
            ).scalars().all()
        check("refused save changed nothing", unchanged.name == "ZZ Aggregate Saved", f"name={unchanged.name}")
        check(
            "refused stale save wrote no audit",
            len(stale_audit) == baseline + 1,
            f"n={len(stale_audit)}",
        )

        # ---------------------- refused save leaves no partial aggregate
        good_token = body["updated_at"]
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json=_aggregate(
                "ZZ Atomic",
                good_token,
                # lone latitude violates the coordinate pair rule
                latitude=52.52,
            ),
        )
        check("invalid aggregate -> 422", r.status_code == 422, f"status={r.status_code} body={r.text[:160]}")

        async with AsyncSessionLocal() as session:
            after = (
                await session.execute(select(Service).where(Service.id == sid))
            ).scalars().first()
            after_contacts = (
                await session.execute(select(ServiceContact).where(ServiceContact.service_id == sid))
            ).scalars().all()
            after_audit = (
                await session.execute(
                    select(AdminAuditLog).where(AdminAuditLog.target_id == str(sid))
                )
            ).scalars().all()
        check("no partial scalar write", after.name == "ZZ Aggregate Saved", f"name={after.name}")
        check("no partial coordinate write", after.latitude is None, f"lat={after.latitude}")
        check("no partial contact write", len(after_contacts) == 1, f"n={len(after_contacts)}")
        check(
            "refused invalid save wrote no audit",
            len(after_audit) == baseline + 1,
            f"n={len(after_audit)}",
        )

        # --------------------- retired category cannot be newly assigned
        r = await client.patch(
            f"{PREFIX}/categories/{secondary['id']}",
            headers=headers,
            json={"is_active": False},
        )
        check("deactivate secondary category", r.status_code == 200, f"status={r.status_code}")

        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json=_aggregate(
                "ZZ Retire",
                after.updated_at.isoformat(),
                categories=[{"category_id": secondary["id"], "is_primary": True}],
            ),
        )
        check("retired category as new primary -> 422", r.status_code == 422, f"status={r.status_code}")

        # an already-assigned retired category may remain in place
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json=_aggregate(
                "ZZ Keep Existing",
                after.updated_at.isoformat(),
                categories=[
                    {"category_id": primary["id"], "is_primary": True},
                    {"category_id": secondary["id"], "is_primary": False},
                ],
            ),
        )
        check("existing retired assignment preserved", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")


async def main() -> None:
    token, admin_id = await _admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    created: dict[str, list] = {"services": [], "categories": []}

    try:
        await _run(headers, admin_id, created)
    finally:
        async with AsyncSessionLocal() as session:
            if created["services"]:
                ids = created["services"]
                await session.execute(delete(ServiceContact).where(ServiceContact.service_id.in_(ids)))
                await session.execute(delete(ServiceCategory).where(ServiceCategory.service_id.in_(ids)))
                await session.execute(delete(Service).where(Service.id.in_(ids)))
            if created["categories"]:
                await session.execute(delete(Category).where(Category.id.in_(created["categories"])))
            targets = [str(x) for x in (created["services"] + created["categories"])]
            if targets:
                await session.execute(delete(AdminAuditLog).where(AdminAuditLog.target_id.in_(targets)))
            await session.commit()
            print(
                "cleanup: removed",
                len(created["services"]),
                "service(s),",
                len(created["categories"]),
                "category/categories, and their audit rows",
            )
        await engine.dispose()

    if failures:
        raise AssertionError(f"{len(failures)} check(s) failed: {failures}")
    print("PASS: service aggregate endpoint checks")


if __name__ == "__main__":
    asyncio.run(main())