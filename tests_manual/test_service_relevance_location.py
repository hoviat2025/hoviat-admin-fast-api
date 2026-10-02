"""Database-backed checks for the location + tri-state relevance pass, and the
hardening items that need real rows.

Covers:
  * `state` (Bundesland) persisting through create / read / patch / aggregate save
  * Germany as the default country
  * all four relevance signals accepting true / false / null, independently
  * tri-state admin filters distinguishing yes / no / unknown
  * `expected_updated_at` being required, and a stale token returning 409
  * a published service's primary category refusing deactivation
  * meaningful aggregate audit diffs (real before/after, not counts)

Run:  venv\\Scripts\\python.exe -m tests_manual.test_service_relevance_location
"""

import asyncio
from typing import Optional

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


async def _token() -> tuple[str, int]:
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


async def _make_service(client: AsyncClient, headers: dict, **over) -> dict:
    body = {"name": "ZZ Loc Service"}
    body.update(over)
    r = await client.post(f"{PREFIX}/services/", headers=headers, json=body)
    check(f"create {body['name']}", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    return r.json()["data"]


async def _new_category(client: AsyncClient, headers: dict, slug: str) -> dict:
    r = await client.post(
        f"{PREFIX}/categories/", headers=headers, json={"name": f"ZZ {slug}", "slug": slug}
    )
    check(f"create category {slug}", r.status_code == 200, f"status={r.status_code}")
    return r.json()["data"]


async def _run(headers: dict, admin_id: int, created: dict) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
        # ==================================================== Germany + Bundesland
        svc = await _make_service(client, headers)
        sid = svc["id"]
        created["services"].append(sid)

        check("country defaults to Germany", svc["country"] == "Germany", f"country={svc['country']}")
        check("state defaults to empty", svc["state"] is None, f"state={svc['state']}")
        check(
            "relevance defaults to unknown",
            all(svc[f] is None for f in
                ("persian_owned", "persian_provider", "persian_language", "persian_service")),
            f"values={[svc[f] for f in ('persian_owned','persian_provider','persian_language','persian_service')]}",
        )

        # --------------------------------------- all four signals, all 3 states
        r = await client.patch(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={
                "state": "Hessen",
                "city": "Frankfurt am Main",
                "postal_code": "60311",
                "address": "Zeil 1",
                "relevance": {
                    "persian_owned": False,
                    "persian_provider": True,
                    "persian_language": None,
                    "persian_service": False,
                },
            },
        )
        check("patch sets state + relevance", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        body = r.json()["data"]
        check("state persisted", body["state"] == "Hessen", f"state={body['state']}")
        check("owner false kept", body["persian_owned"] is False)
        check("provider true kept", body["persian_provider"] is True)
        check("language stays unknown (null)", body["persian_language"] is None)
        check("service false kept", body["persian_service"] is False)

        # ---------------------------------- provider independent of owner etc.
        # A German-owned clinic with an Iranian dentist, and Persian spoken.
        r = await client.patch(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"relevance": {"persian_language": True}},
        )
        body = r.json()["data"]
        check("language set true", body["persian_language"] is True)
        check("owner unaffected by language change", body["persian_owned"] is False)
        check("provider unaffected by language change", body["persian_provider"] is True)

        # Explicitly back to unknown via a partial update.
        r = await client.patch(
            f"{PREFIX}/services/{sid}", headers=headers, json={"relevance": {"persian_provider": None}}
        )
        body = r.json()["data"]
        check("explicit null resets to unknown", body["persian_provider"] is None)
        check("other signals survive the reset", body["persian_owned"] is False and body["persian_language"] is True)

        # --------------------------------------------------- aggregate save
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={
                "name": "ZZ Loc Saved",
                "state": "Berlin",
                "city": "Berlin",
                "country": "Germany",
                "persian_owned": True,
                "persian_provider": None,
                "persian_language": None,
                "persian_service": None,
                "status": ServiceStatus.draft.value,
                "expected_updated_at": body["updated_at"],
            },
        )
        check("aggregate save accepted", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        saved = r.json()["data"]
        check("aggregate persisted state", saved["state"] == "Berlin", f"state={saved['state']}")
        check("aggregate kept true", saved["persian_owned"] is True)
        check(
            "aggregate kept three unknowns",
            saved["persian_provider"] is None and saved["persian_language"] is None and saved["persian_service"] is None,
        )

        async with AsyncSessionLocal() as session:
            row = (await session.execute(select(Service).where(Service.id == sid))).scalars().first()
        check("state really in the row", row.state == "Berlin", f"state={row.state}")
        check("nulls really null in the row", row.persian_provider is None and row.persian_service is None)

        # ------------------------------------------- expected_updated_at required
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"name": "ZZ No Token", "status": ServiceStatus.draft.value},
        )
        check("missing expected_updated_at refused", r.status_code == 422, f"status={r.status_code} body={r.text[:160]}")

        async with AsyncSessionLocal() as session:
            unchanged = (await session.execute(select(Service).where(Service.id == sid))).scalars().first()
        check("refused save changed nothing", unchanged.name == "ZZ Loc Saved", f"name={unchanged.name}")

        # ------------------------------------------------------- stale -> 409
        stale_token = saved["updated_at"]
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"name": "ZZ First Move", "status": ServiceStatus.draft.value, "expected_updated_at": stale_token},
        )
        check("first aggregate save ok", r.status_code == 200, f"status={r.status_code}")
        moved = r.json()["data"]["updated_at"]

        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"name": "ZZ Second Move", "status": ServiceStatus.draft.value, "expected_updated_at": stale_token},
        )
        check("stale token -> 409", r.status_code == 409, f"status={r.status_code}")

        # The stale-save token must not have been consumed; the current value
        # still works.
        r = await client.put(
            f"{PREFIX}/services/{sid}",
            headers=headers,
            json={"name": "ZZ Third Move", "status": ServiceStatus.draft.value, "expected_updated_at": moved},
        )
        check("latest token still valid", r.status_code == 200, f"status={r.status_code}")

        # ----------------------------------------- tri-state admin filtering
        yn_svc = await _make_service(
            client, headers, name="ZZ Yes Provider",
            state="Bayern", city="München",
            persian_provider=True, persian_language=True,
        )
        unknown_svc = await _make_service(
            client, headers, name="ZZ Unknown Provider", state="Bayern", city="München",
        )
        no_svc = await _make_service(
            client, headers, name="ZZ No Provider",
            state="Nordrhein-Westfalen", city="Köln", persian_provider=False,
        )
        created["services"] += [yn_svc["id"], unknown_svc["id"], no_svc["id"]]

        async def search(**params):
            r = await client.get(f"{PREFIX}/services/", headers=headers, params=params)
            assert r.status_code == 200, r.text[:200]
            return {s["id"] for s in r.json()["data"]}

        yes = await search(persian_provider="yes")
        check("filter yes finds only yes", yn_svc["id"] in yes and no_svc["id"] not in yes and unknown_svc["id"] not in yes, f"n={len(yes)}")

        no = await search(persian_provider="no")
        check("filter no finds only no", no_svc["id"] in no and yn_svc["id"] not in no, f"n={len(no)}")

        unknown = await search(persian_provider="unknown")
        check("filter unknown finds only unknown", unknown_svc["id"] in unknown and yn_svc["id"] not in unknown, f"n={len(unknown)}")

        lower_bayern = await search(state="bayern")
        check(
            "state filter is case-insensitive",
            {yn_svc["id"], unknown_svc["id"]}.issubset(lower_bayern),
            f"n={len(lower_bayern)}",
        )

        # A Bundesland that is not stored must not match by substring.
        hessen = await search(state="Hessen")
        check(
            "state filter is an exact match, not a prefix",
            yn_svc["id"] not in hessen and no_svc["id"] not in hessen,
            f"n={len(hessen)}",
        )

        # The aggregate save replaces the whole state, so a save that omits
        # `state` clears it. Assert that explicitly rather than by accident.
        async with AsyncSessionLocal() as session:
            cleared = (await session.execute(select(Service).where(Service.id == sid))).scalars().first()
        check(
            "aggregate save clears an omitted state",
            cleared.state is None,
            f"state={cleared.state!r}",
        )

        bayern = await search(state="Bayern")
        check(
            "state filter is independent of relevance",
            {yn_svc["id"], unknown_svc["id"]}.issubset(bayern),
            f"n={len(bayern)}",
        )

        both = await search(state="Bayern", persian_provider="yes")
        check(
            "state and relevance filters combine",
            both == {yn_svc["id"]},
            f"got={len(both)}",
        )

        # ============================ published primary cannot be deactivated
        primary = await _new_category(client, headers, "zz-deact-primary")
        secondary = await _new_category(client, headers, "zz-deact-secondary")
        created["categories"] += [primary["id"], secondary["id"]]

        pub = await _make_service(client, headers, name="ZZ Published")
        created["services"].append(pub["id"])
        r = await client.put(
            f"{PREFIX}/services/{pub['id']}",
            headers=headers,
            json={
                "name": "ZZ Published",
                "status": ServiceStatus.published.value,
                "categories": [
                    {"category_id": primary["id"], "is_primary": True},
                    {"category_id": secondary["id"], "is_primary": False},
                ],
                "expected_updated_at": pub["updated_at"],
            },
        )
        check("published with active primary", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

        r = await client.patch(
            f"{PREFIX}/categories/{primary['id']}", headers=headers, json={"is_active": False}
        )
        check(
            "deactivating a published primary refused",
            r.status_code == 409,
            f"status={r.status_code} body={r.text[:220]}",
        )
        check("refusal names the blocking services", "ZZ Published" in r.text, "")

        async with AsyncSessionLocal() as session:
            cat = (await session.execute(select(Category).where(Category.id == primary["id"]))).scalars().first()
            links = (
                await session.execute(
                    select(ServiceCategory).where(ServiceCategory.category_id == primary["id"])
                )
            ).scalars().all()
        check("category still active after refusal", cat.is_active is True)
        check("links untouched after refusal", len(links) == 1 and links[0].is_primary is True)

        # Reassign the primary, then the category may be retired.
        current = r.json()["data"]
        pub_now = await client.get(f"{PREFIX}/services/{pub['id']}", headers=headers)
        pub_body = pub_now.json()["data"]
        r = await client.put(
            f"{PREFIX}/services/{pub['id']}",
            headers=headers,
            json={
                "name": pub_body["name"],
                "description": pub_body.get("description"),
                "state": pub_body.get("state"),
                "city": pub_body.get("city"),
                "country": pub_body.get("country"),
                "status": ServiceStatus.published.value,
                "categories": [{"category_id": secondary["id"], "is_primary": True}],
                "expected_updated_at": pub_body["updated_at"],
            },
        )
        check("reassigned primary", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

        r = await client.patch(
            f"{PREFIX}/categories/{primary['id']}", headers=headers, json={"is_active": False}
        )
        check("deactivation allowed once reassigned", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")

        # ================================== meaningful aggregate audit diff
        audited = await _make_service(client, headers, name="ZZ Audit Start", city="Kiel")
        created["services"].append(audited["id"])
        before_audit = await _audit_count(audited["id"])

        r = await client.put(
            f"{PREFIX}/services/{audited['id']}",
            headers=headers,
            json={
                "name": "ZZ Audit Renamed",
                "city": "Hamburg",
                "state": "Schleswig-Holstein",
                "status": ServiceStatus.draft.value,
                "persian_service": True,
                "contacts": [
                    {"title": "Phone", "type": "phone", "value": "+49 40 111", "display_order": 0, "is_visible": True}
                ],
                "categories": [{"category_id": secondary["id"], "is_primary": True}],
                "expected_updated_at": audited["updated_at"],
            },
        )
        check("audited save ok", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

        changes = await _last_changes(audited["id"], "service.save")
        check("audit row written", changes is not None, "")
        if changes is not None:
            check("audit records name change", changes.get("name") == {"before": "ZZ Audit Start", "after": "ZZ Audit Renamed"}, f"{changes.get('name')}")
            check("audit records city change", changes.get("city") == {"before": "Kiel", "after": "Hamburg"}, f"{changes.get('city')}")
            check(
                "audit records state change",
                changes.get("state") == {"before": None, "after": "Schleswig-Holstein"},
                f"{changes.get('state')}",
            )
            check("audit records tri-state change", changes.get("persian_service") == {"before": None, "after": True}, f"{changes.get('persian_service')}")
            contacts = changes.get("contacts") or {}
            check(
                "audit records contact values, not a count",
                contacts.get("before") == [] and any(row["value"] == "+49 40 111" for row in contacts.get("after") or []),
                f"contacts={contacts}",
            )
            cats = changes.get("categories") or {}
            check(
                "audit records category ids and primary flag",
                cats.get("before") == [] and cats.get("after") == [{"category_id": secondary["id"], "is_primary": True}],
                f"categories={cats}",
            )
            check(
                "audit omits unchanged fields",
                "country" not in changes and "updated_at" not in changes,
                f"keys={sorted(changes)}",
            )
        check("audit added exactly one row", await _audit_count(audited["id"]) == before_audit + 1)

        # A partial update that changes a tri-state signal must also be audited.
        r = await client.patch(
            f"{PREFIX}/services/{audited['id']}",
            headers=headers,
            json={"relevance": {"persian_provider": True}},
        )
        check("provider set yes", r.status_code == 200 and r.json()["data"]["persian_provider"] is True, f"status={r.status_code}")

        patch_before = await _audit_count(audited["id"])
        r = await client.patch(
            f"{PREFIX}/services/{audited['id']}",
            headers=headers,
            json={"relevance": {"persian_owned": True, "persian_provider": None}},
        )
        check("relevance patch accepted", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")

        patch_changes = await _last_changes(audited["id"], "service.update")
        check("partial relevance update is audited", patch_changes is not None, "")
        if patch_changes is not None:
            check(
                "audit records the owner signal change",
                patch_changes.get("persian_owned") == {"before": None, "after": True},
                f"{patch_changes.get('persian_owned')}",
            )
            check(
                "audit records setting a signal back to unknown",
                patch_changes.get("persian_provider") == {"before": True, "after": None},
                f"{patch_changes.get('persian_provider')}",
            )
            check(
                "audit omits signals the patch did not touch",
                "persian_service" not in patch_changes,
                f"keys={sorted(patch_changes)}",
            )
        check("patch audit added exactly one row", await _audit_count(audited["id"]) == patch_before + 1)


async def _last_changes(service_id: int, action: str) -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(AdminAuditLog)
                .where(
                    AdminAuditLog.target_id == str(service_id),
                    AdminAuditLog.action == action,
                )
                .order_by(AdminAuditLog.id.desc())
                .limit(1)
            )
        ).scalars().first()
        return row.changes if row else None


async def _audit_count(service_id: int) -> int:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AdminAuditLog).where(AdminAuditLog.target_id == str(service_id))
            )
        ).scalars().all()
    return len(rows)


async def main() -> None:
    token, admin_id = await _token()
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
    print("PASS: service location + relevance checks")


if __name__ == "__main__":
    asyncio.run(main())