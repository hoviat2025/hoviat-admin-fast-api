"""Concurrency regression for the category/primary invariant.

The rule under test:

    A published service must have an active primary category.

Two operations can break it if they do not share a lock:

    (A) a service write that publishes / assigns a category as primary, and
    (B) a category deactivation.

Without coordination this interleaving is possible:

    A: reads category C, sees is_active = true
    B: reads published services, sees none using C
    B: sets C inactive, commits
    A: commits, publishing a service whose primary category is now inactive

The fix is a shared row lock: both sides take SELECT ... FOR UPDATE on the
category row before deciding. These tests drive real transactions against the
local database and assert the loser is actually BLOCKED and then refuses once
the winner commits.

Scenarios covered:
  1. deactivation wins  -> the service save blocks, then fails
  2. service save wins  -> the deactivation blocks, then fails
  3. publishing via the PATCH status endpoint respects the same rule
  4. several concurrent saves on overlapping category sets do not deadlock

Run:  venv\\Scripts\\python.exe -m tests_manual.test_category_publish_concurrency
"""

import asyncio
import contextlib

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from app.core.database import AsyncSessionLocal, engine
from app.core.exceptions import ServiceError
from app.core.security import create_access_token
from app.main import app
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact
from app.modules.services.repositories.service_categories import (
    ServiceCategoryRepository,
)
from app.modules.services.schemas.category_requests import CategoryUpdateRequest
from app.modules.services.services.category_service import CategoryService
from app.modules.services.services.service_service import ServiceService

PREFIX = "/api/admin/service-management"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"[PASS] {label}" + (f" :: {detail}" if detail else ""))
    else:
        failures.append(label)
        print(f"[FAIL] {label}" + (f" :: {detail}" if detail else ""))


# How long to wait before declaring a task "not blocked". Row-lock waits in
# PostgreSQL have no timeout, so a correct implementation simply never returns.
BLOCK_PROBE_SECONDS = 1.5


async def _token() -> str:
    async with AsyncSessionLocal() as session:
        admin = (
            await session.execute(
                select(Admin).where(Admin.is_active == True).order_by(Admin.id)  # noqa: E712
            )
        ).scalars().first()
        if admin is None:
            raise RuntimeError("no active admin in the local database")
        return create_access_token(
            data={"sub": str(admin.id), "role": "admin", "super": admin.is_superadmin},
            expires_delta=None,
        )


async def _new_category(client: AsyncClient, headers: dict, slug: str) -> dict:
    r = await client.post(
        f"{PREFIX}/categories/", headers=headers, json={"name": f"ZZ {slug}", "slug": slug}
    )
    check(f"create category {slug}", r.status_code == 200, f"status={r.status_code}")
    return r.json()["data"]


async def _new_service(client: AsyncClient, headers: dict, name: str) -> dict:
    r = await client.post(f"{PREFIX}/services/", headers=headers, json={"name": name})
    check(f"create service {name}", r.status_code == 200, f"status={r.status_code}")
    return r.json()["data"]


async def _category_is_active(category_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(text("select is_active from categories where id = :i"), {"i": category_id})
        ).first()
        return bool(row[0])


async def _published_primaries(category_id: int) -> list[int]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    select s.id
                    from services s
                    join service_categories sc
                      on sc.service_id = s.id and sc.category_id = :cat and sc.is_primary
                    where s.status = 'published'
                    order by s.id
                    """
                ),
                {"cat": category_id},
            )
        ).fetchall()
        return [r[0] for r in rows]


# ------------------------------------------------------------------ scenario 1


async def _deactivation_wins(client: AsyncClient, headers: dict, cat_id: int, svc: dict) -> None:
    """
    Deactivation commits first; the concurrent service publish must fail.

    The deactivation is driven from an explicit transaction that is deliberately
    left uncommitted, so the category lock is held while the service save runs.
    """
    async with AsyncSessionLocal() as deact:
        await deact.begin()
        repo_cat = CategoryService(deact).repo
        category = await repo_cat.get_for_update(cat_id)
        check("deactivation side holds the category lock", category is not None)

        # Emulate the deactivation's decision + write, without committing yet.
        links = ServiceCategoryRepository(deact)
        blocking = await links.published_services_with_primary(cat_id)
        check("nothing published uses the category yet", len(blocking) == 0, f"n={len(blocking)}")
        await repo_cat.update(cat_id, {"is_active": False})

        async def publish() -> str:
            """The real domain call, in its own session/transaction."""
            async with AsyncSessionLocal() as s:
                try:
                    await ServiceService(s).save_aggregate(
                        svc["id"],
                        _publish_payload(svc, cat_id),
                    )
                    return "saved"
                except ServiceError as exc:
                    return f"{exc.status_code}"

        task = asyncio.create_task(publish())
        await asyncio.sleep(BLOCK_PROBE_SECONDS)
        blocked = not task.done()
        check("concurrent publish is blocked by the category lock", blocked, "")

        await deact.commit()  # the winner commits and releases the lock

        outcome = await asyncio.wait_for(task, timeout=30)
        check("publish fails after the deactivation commits", outcome == "422", f"outcome={outcome}")

    check("category is inactive", not await _category_is_active(cat_id))
    check("no published service kept the inactive primary", await _published_primaries(cat_id) == [])


# ------------------------------------------------------------------ scenario 2


async def _service_save_wins(client: AsyncClient, headers: dict, cat_id: int, svc: dict) -> None:
    """
    The service publish commits first; the concurrent deactivation must fail.

    A transaction holds the category lock on behalf of the pending publish, the
    deactivation is launched and observed to block, then the publish is committed.
    """
    async with AsyncSessionLocal() as publisher:
        await publisher.begin()
        # Same lock the real save takes, so the deactivation below contends for
        # exactly the row the publish depends on.
        repo_cat = CategoryService(publisher).repo
        category = await repo_cat.get_for_update(cat_id)
        check("publish side holds the category lock", category is not None)

        # Write the publish as the real save would, but commit it ourselves.
        links = ServiceCategoryRepository(publisher)
        domain = ServiceService(publisher)
        pairs = [(cat_id, True)]
        await domain._validate_category_state(
            pairs, service_id=svc["id"], resulting_status=ServiceStatus.published
        )
        await links.replace(svc["id"], [{"category_id": cat_id, "is_primary": True}])
        await domain.services.update(
            svc["id"], {"status": ServiceStatus.published.value}
        )
        await publisher.flush()

        async def deactivate() -> str:
            async with AsyncSessionLocal() as s:
                try:
                    await CategoryService(s).update(
                        cat_id, CategoryUpdateRequest(is_active=False)
                    )
                    return "deactivated"
                except ServiceError as exc:
                    return f"{exc.status_code}"

        task = asyncio.create_task(deactivate())
        await asyncio.sleep(BLOCK_PROBE_SECONDS)
        check("concurrent deactivation is blocked by the category lock", not task.done(), "")

        await publisher.commit()  # the winner commits and releases the lock

        outcome = await asyncio.wait_for(task, timeout=30)
        check("deactivation fails after the publish commits", outcome == "409", f"outcome={outcome}")

    check("category stayed active", await _category_is_active(cat_id))
    check(
        "the published service is what blocks the deactivation",
        svc["id"] in await _published_primaries(cat_id),
    )


# ------------------------------------------------------------------ scenario 3


async def _status_endpoint_respects_the_rule(
    client: AsyncClient, headers: dict, cat_id: int, svc: dict, retired_cat_id: int
) -> None:
    """
    Publishing through PATCH /status must obey the same rule.

    Regression for a gap that was not even a race: the status path used a
    count-only check, so a service whose primary category had already been
    retired could be published through this endpoint.
    """
    r = await client.put(
        f"{PREFIX}/services/{cat_id and svc['id']}",
        headers=headers,
        json={
            "name": "ZZ Status Path",
            "status": ServiceStatus.draft.value,
            "categories": [{"category_id": cat_id, "is_primary": True}],
            "expected_updated_at": svc["updated_at"],
        },
    )
    check("prepare service for status-path check", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    current = r.json()["data"]

    # Retire the primary category while the service is still a draft.
    r = await client.patch(
        f"{PREFIX}/categories/{cat_id}", headers=headers, json={"is_active": False}
    )
    check("retire the primary category of a draft", r.status_code == 200, f"status={r.status_code}")

    r = await client.patch(
        f"{PREFIX}/services/{svc['id']}/status",
        headers=headers,
        json={"status": ServiceStatus.published.value},
    )
    check(
        "status endpoint refuses to publish on an inactive primary",
        r.status_code == 422,
        f"status={r.status_code} body={r.text[:200]}",
    )
    check(
        "status endpoint error explains the active-primary rule",
        "active primary" in r.text.lower(),
        "",
    )

    # The aggregate save must refuse the same thing.
    r = await client.put(
        f"{PREFIX}/services/{svc['id']}",
        headers=headers,
        json={
            "name": "ZZ Status Path",
            "status": ServiceStatus.published.value,
            "categories": [{"category_id": cat_id, "is_primary": True}],
            "expected_updated_at": current["updated_at"],
        },
    )
    check(
        "aggregate save refuses to publish on an inactive primary",
        r.status_code == 422,
        f"status={r.status_code}",
    )
    check("no published service kept the inactive primary", await _published_primaries(cat_id) == [])


# ------------------------------------------------------------------ scenario 4


async def _concurrent_saves_do_not_deadlock(headers: dict, cats: list[int]) -> list[int]:
    """
    Overlapping category sets locked in ascending id order must not deadlock.

    Two saves referencing the SAME categories in OPPOSITE order are the classic
    deadlock trigger if locks are taken in request order.

    Returns the created service ids so the caller can clean them up.
    """

    async def save(order: list[int], tag: str) -> int | None:
        async with AsyncSessionLocal() as s:
            try:
                svc = await ServiceService(s).create(
                    _create_payload(tag, order)
                )
                return svc.id
            except ServiceError:
                return None

    outcomes = await asyncio.gather(
        save(list(cats), "ZZ DL A"),
        save(list(reversed(cats)), "ZZ DL B"),
        save(list(cats), "ZZ DL C"),
    )
    check(
        "overlapping saves in opposite orders all complete",
        all(item is not None for item in outcomes),
        f"outcomes={outcomes}",
    )
    return [item for item in outcomes if item is not None]


def _publish_payload(svc: dict, cat_id: int):
    from app.modules.services.schemas.service_requests import (
        ServiceAggregateSaveRequest,
    )

    return ServiceAggregateSaveRequest(
        name=svc["name"],
        status=ServiceStatus.published,
        categories=[{"category_id": cat_id, "is_primary": True}],
        expected_updated_at=svc["updated_at"],
    )


def _create_payload(tag: str, order: list[int]):
    from app.modules.services.schemas.service_requests import ServiceCreateRequest

    return ServiceCreateRequest(
        name=tag,
        status=ServiceStatus.draft,
        categories=[
            {"category_id": cat_id, "is_primary": index == 0}
            for index, cat_id in enumerate(order)
        ],
    )


async def _run(headers: dict, created: dict) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
        # ---- scenario 1: deactivation wins
        cat1 = await _new_category(client, headers, "zz-conc-a")
        svc1 = await _new_service(client, headers, "ZZ Concurrency A")
        created["services"].append(svc1["id"])
        created["categories"].append(cat1["id"])
        await _deactivation_wins(client, headers, cat1["id"], svc1)

        # ---- scenario 2: service publish wins
        cat2 = await _new_category(client, headers, "zz-conc-b")
        svc2 = await _new_service(client, headers, "ZZ Concurrency B")
        created["services"].append(svc2["id"])
        created["categories"].append(cat2["id"])
        await _service_save_wins(client, headers, cat2["id"], svc2)

        # ---- scenario 3: the status endpoint path
        cat3 = await _new_category(client, headers, "zz-conc-c")
        svc3 = await _new_service(client, headers, "ZZ Concurrency C")
        created["services"].append(svc3["id"])
        created["categories"].append(cat3["id"])
        await _status_endpoint_respects_the_rule(client, headers, cat3["id"], svc3, cat3["id"])

        # ---- scenario 4: overlapping saves, opposite category order
        cat4a = await _new_category(client, headers, "zz-conc-d1")
        cat4b = await _new_category(client, headers, "zz-conc-d2")
        created["categories"] += [cat4a["id"], cat4b["id"]]
        created["services"] += await _concurrent_saves_do_not_deadlock(
            headers, [cat4a["id"], cat4b["id"]]
        )


async def main() -> None:
    headers = {"Authorization": f"Bearer {await _token()}"}
    created: dict[str, list] = {"services": [], "categories": []}

    try:
        await _run(headers, created)
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
    print("PASS: category / published-primary concurrency invariants")


if __name__ == "__main__":
    asyncio.run(main())