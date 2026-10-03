"""
End-to-end DB/API coverage for the international location model, the shared
service query layer, the public search endpoint and the location facets.

Exercises the real HTTP surface against the local development database.

Run:  venv\\Scripts\\python.exe -m tests_manual.test_service_public_search
"""

import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.main import app
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact

ADMIN_PREFIX = "/api/admin/service-management"
PUBLIC_PREFIX = "/api/services"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"[PASS] {label}" + (f" :: {detail}" if detail else ""))
    else:
        failures.append(label)
        print(f"[FAIL] {label}" + (f" :: {detail}" if detail else ""))


async def _headers() -> dict:
    async with AsyncSessionLocal() as session:
        admin = (
            await session.execute(
                select(Admin).where(Admin.is_active == True).order_by(Admin.id)  # noqa: E712
            )
        ).scalars().first()
        if admin is None:
            raise RuntimeError("no active admin in the local database")
        token = create_access_token(
            data={"sub": str(admin.id), "role": "admin", "super": admin.is_superadmin},
            expires_delta=None,
        )
        return {"Authorization": f"Bearer {token}"}


async def _make_category(client, headers, name, slug, parent_id=None):
    r = await client.post(
        f"{ADMIN_PREFIX}/categories/",
        headers=headers,
        json={"name": name, "slug": slug, "parent_id": parent_id},
    )
    check(f"create category {slug}", r.status_code == 200, f"status={r.status_code} body={r.text[:140]}")
    return r.json()["data"]


async def _make_service(client, headers, name, **over):
    """
    Create a service as a DRAFT, then publish it if the caller asked for it.

    Publishing requires at least one primary category, so a helper cannot simply
    post status=published with location fields and no categories. This creates the
    draft, then performs the aggregate publish that the real editor would use, so
    the test exercises the same path as production.
    """
    body = {"name": name}
    body.update({k: v for k, v in over.items() if k != "status"})
    r = await client.post(f"{ADMIN_PREFIX}/services/", headers=headers, json=body)
    if r.status_code != 200:
        check(f"create service {name}", False, f"status={r.status_code} body={r.text[:200]}")
        raise RuntimeError("could not create fixture service")
    created = r.json()["data"]

    if over.get("status") != ServiceStatus.published.value:
        check(f"create service {name}", True, f"id={created['id']}")
        return created

    publish_body = {"name": name, "status": ServiceStatus.published.value}
    publish_body.update({k: v for k, v in over.items() if k != "status"})
    publish_body["expected_updated_at"] = created["updated_at"]
    r = await client.put(
        f"{ADMIN_PREFIX}/services/{created['id']}", headers=headers, json=publish_body
    )
    check(
        f"create+publish service {name}",
        r.status_code == 200,
        f"status={r.status_code} body={r.text[:200]}",
    )
    return r.json()["data"] if r.status_code == 200 else created


async def _public(client, **params):
    r = await client.get(f"{PUBLIC_PREFIX}/services/", params=params)
    return r


async def _assert_public_rejects(client, headers, label, key, value):
    """
    Assert that a parameter the public surface must not expose is refused.

    The public schema uses `extra="forbid"`, so an unknown parameter is a 422
    rather than a silently ignored no-op. Verifying through the real endpoint
    matters: a filter that is merely absent from the allow-list would still be
    ignored by FastAPI, which would make the check pass for the wrong reason.
    """
    r = await client.get(f"{PUBLIC_PREFIX}/services/", params={key: value})
    if r.status_code == 422:
        check(label, True, "rejected with 422")
    else:
        # Distinguish "correctly refused" from "accepted but ignored", and report
        # which happened so the cause is obvious.
        check(
            label,
            False,
            f"status={r.status_code} (query parameter was accepted, expected 422)",
        )


# =============================================================== location model


async def _test_location_model(client, headers, created):
    print("--- international / generic location ---")

    # --- DE works, and other countries need no schema change at all
    de = await _make_service(client, headers, "ZZ Berlin Praxis", state="Hessen", city="Frankfurt am Main")
    created["services"].append(de["id"])
    check("country_code defaults to DE", de["country_code"] == "DE", f"got={de['country_code']}")
    check("state stored canonically", de["state"] == "Hessen", f"got={de['state']}")

    # One published service per non-German country, so the public search and the
    # facet endpoint have real non-DE data to work with. The category argument is
    # supplied lazily below, once the tree exists.
    non_german: list = []
    for code in ("AT", "CH", "NL", "US"):
        svc = await _make_service(
            client, headers, f"ZZ {code} Service",
            country_code=code.lower(), city="Vienna", state="Wien", postal_code="1010",
        )
        created["services"].append(svc["id"])
        check(
            f"country {code} accepted without schema change",
            svc["country_code"] == code,
            f"got={svc['country_code']}",
        )
        check(f"{code} free-text state preserved", svc["state"] == "Wien", f"got={svc['state']}")
        non_german.append((code, svc))

    # --- postal codes are generic text, not German 5-digit
    for plz in ("10115", "SW1A 1AA", "K1A 0B1"):
        svc = await _make_service(
            client, headers, f"ZZ PLZ {plz}", country_code="NL", postal_code=plz
        )
        created["services"].append(svc["id"])
        check(f"postal code {plz!r} accepted", svc["postal_code"] == plz, f"got={svc['postal_code']}")

    # --- German state variants normalise to one canonical value
    for variant, expected in [
        ("Hesse", "Hessen"),
        ("hessen", "Hessen"),
        ("HESSEN", "Hessen"),
        ("HE", "Hessen"),
        ("thueringen", "Thüringen"),
        ("Thuringia", "Thüringen"),
        ("Baden-Wurttemberg", "Baden-Württemberg"),
    ]:
        r = await client.patch(
            f"{ADMIN_PREFIX}/services/{de['id']}", headers=headers, json={"state": variant}
        )
        check(
            f"state variant {variant!r} -> {expected}",
            r.status_code == 200 and r.json()["data"]["state"] == expected,
            f"status={r.status_code} state={r.json()['data']['state'] if r.status_code == 200 else r.text[:100]}",
        )

    # --- an unsupported variant is refused rather than stored as a duplicate
    r = await client.patch(
        f"{ADMIN_PREFIX}/services/{de['id']}", headers=headers, json={"state": "Hesse-Nassau"}
    )
    check(
        "unknown German state variant refused",
        r.status_code == 422,
        f"status={r.status_code}",
    )

    async with AsyncSessionLocal() as session:
        stored = (
            await session.execute(
                text("select state from services where id = :i"), {"i": de["id"]}
            )
        ).first()
    check(
        "refused state was not persisted",
        stored[0] == "Baden-Württemberg",
        f"state={stored[0]!r}",
    )

    # --- one canonical row, not one per spelling
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text("select distinct state from services where state is not null")
            )
        ).fetchall()
    states = sorted(r[0] for r in rows)
    check(
        "no duplicate canonical German states stored",
        "Hesse" not in states and "hessen" not in states,
        f"states={states}",
    )

    # --- a bad country code is refused
    r = await client.patch(
        f"{ADMIN_PREFIX}/services/{de['id']}", headers=headers, json={"country_code": "DEU"}
    )
    check("three-letter country refused", r.status_code == 422, f"status={r.status_code}")

    # --- blank country means unstated, not Germany
    r = await client.patch(
        f"{ADMIN_PREFIX}/services/{de['id']}", headers=headers, json={"country_code": ""}
    )
    check(
        "blank country becomes unstated",
        r.status_code == 200 and r.json()["data"]["country_code"] is None,
        f"status={r.status_code} value={r.json()['data']['country_code'] if r.status_code == 200 else ''}",
    )
    await client.patch(
        f"{ADMIN_PREFIX}/services/{de['id']}", headers=headers, json={"country_code": "DE"}
    )

    return de, non_german


# ================================================================== search


async def _test_search(client, headers, created, non_german):
    print("--- search ---")

    # A category tree: parent -> child -> grandchild, to prove descendants work.
    parent = await _make_category(client, headers, "ZZ Restaurants", "zz-restaurants")
    child = await _make_category(client, headers, "ZZ Persian Restaurants", "zz-persian-restaurants", parent["id"])
    grandchild = await _make_category(client, headers, "ZZ Kabab", "zz-kabab", child["id"])
    other = await _make_category(client, headers, "ZZ Dentists", "zz-dentists")
    created["categories"] += [parent["id"], child["id"], grandchild["id"], other["id"]]

    # published with the grandchild as its primary category
    deep = await _make_service(
        client, headers, "ZZ Kabab Haus",
        status=ServiceStatus.published.value,
        city="Berlin", state="Berlin",
        persian_language=True, persian_service=True,
        categories=[{"category_id": grandchild["id"], "is_primary": True}],
    )
    created["services"].append(deep["id"])

    # published where the matching category is SECONDARY, not primary
    secondary_only = await _make_service(
        client, headers, "ZZ Secondary Only",
        status=ServiceStatus.published.value,
        categories=[
            {"category_id": other["id"], "is_primary": True},
            {"category_id": parent["id"], "is_primary": False},
        ],
    )
    created["services"].append(secondary_only["id"])

    # an unpublished service that must never appear publicly
    draft = await _make_service(client, headers, "ZZ Hidden Draft", city="Berlin")
    created["services"].append(draft["id"])

    unknown = await _make_service(
        client, headers, "ZZ Unknown Signals",
        status=ServiceStatus.published.value,
        city="Berlin", state="Hessen",
        persian_owned=False, persian_provider=None,
        categories=[{"category_id": other["id"], "is_primary": True}],
    )
    created["services"].append(unknown["id"])

    # ---- published only
    r = await _public(client, q="ZZ")
    ids = [s["id"] for s in r.json()["data"]]
    check("public search returns 200", r.status_code == 200, f"status={r.status_code}")
    check("draft excluded from public search", draft["id"] not in ids, f"ids={ids}")

    # ---- country filter
    # The non-German fixtures are published here (they were created as drafts, so
    # they must be published before public search can see them). This is what
    # proves the endpoint is genuinely international rather than DE-only.
    for code, svc in non_german:
        r = await client.put(
            f"{ADMIN_PREFIX}/services/{svc['id']}", headers=headers,
            json={
                "name": svc["name"], "status": ServiceStatus.published.value,
                "country_code": code, "city": "Vienna", "state": "Wien",
                "categories": [{"category_id": other["id"], "is_primary": True}],
                "expected_updated_at": svc["updated_at"],
            },
        )
        check(f"publish {code} service", r.status_code == 200, f"status={r.status_code} body={r.text[:140]}")

    r = await _public(client, country_code="DE")
    check("country_code=DE works", r.status_code == 200 and len(r.json()["data"]) > 0, f"n={len(r.json().get('data', []))}")
    check(
        "country_code=DE excludes non-DE",
        all(s["country_code"] == "DE" for s in r.json()["data"]),
        f"countries={sorted({s['country_code'] for s in r.json()['data']})}",
    )

    for code, svc in non_german:
        r = await _public(client, country_code=code)
        got = [s["id"] for s in r.json()["data"]]
        check(
            f"country_code={code} returns published {code} services",
            svc["id"] in got and all(s["country_code"] == code for s in r.json()["data"]),
            f"ids={got}",
        )

    # lowercase country code normalises the same way
    r = await _public(client, country_code="at")
    check(
        "country filter is case-insensitive",
        any(s["country_code"] == "AT" for s in r.json()["data"]),
        f"n={len(r.json().get('data', []))}",
    )

    # the endpoint itself must not be Germany-only
    r = await _public(client, country_code="CH")
    check("non-German country query accepted", r.status_code == 200, f"status={r.status_code}")

    # ---- state + city
    r = await _public(client, country_code="DE", state="Berlin", city="Berlin")
    ids = [s["id"] for s in r.json()["data"]]
    check("state + city combination", deep["id"] in ids, f"ids={ids}")

    r = await _public(client, state="berlin")
    check(
        "state filter is case-insensitive",
        any(s["id"] == deep["id"] for s in r.json()["data"]),
        "",
    )

    r = await _public(client, city="BERLIN")
    check(
        "city filter is case-insensitive exact",
        any(s["id"] == deep["id"] for s in r.json()["data"]),
        "",
    )

    r = await _public(client, city="Berl")
    check(
        "city exact does not match a prefix",
        not any(s["id"] == deep["id"] for s in r.json()["data"]),
        f"n={len(r.json().get('data', []))}",
    )

    # ---- relevance: all four, and null != false
    r = await _public(client, persian_language="yes")
    check("persian_language=yes", deep["id"] in [s["id"] for s in r.json()["data"]], "")

    r = await _public(client, persian_service="yes")
    check("persian_service=yes", deep["id"] in [s["id"] for s in r.json()["data"]], "")

    r = await _public(client, persian_owned="no")
    ids = [s["id"] for s in r.json()["data"]]
    check("persian_owned=no finds the explicit-false row", unknown["id"] in ids, f"ids={ids}")

    r = await _public(client, persian_owned="unknown")
    ids = [s["id"] for s in r.json()["data"]]
    check(
        "persian_owned=unknown excludes the explicit-false row",
        unknown["id"] not in ids,
        f"ids={ids}",
    )
    check(
        "unknown and false are different filters",
        [s["id"] for s in (await _public(client, persian_owned="no")).json()["data"]]
        != ids,
        "",
    )

    r = await _public(client, persian_provider="unknown")
    check("persian_provider=unknown", unknown["id"] in [s["id"] for s in r.json()["data"]], "")

    # ---- category hierarchy
    r = await _public(client, category=parent["id"], size=100)
    ids = [s["id"] for s in r.json()["data"]]
    check(
        "parent category includes services tagged only with a descendant",
        deep["id"] in ids,
        f"ids={ids}",
    )
    check(
        "parent category includes services tagged with the parent itself",
        secondary_only["id"] in ids,
        f"ids={ids}",
    )

    # Restricting to the grandchild must narrow the result, which is the point of
    # a hierarchy filter: the parent is a superset of its descendants.
    r_child = await _public(client, category=child["id"], size=100)
    ids_child = set(s["id"] for s in r_child.json()["data"])
    check(
        "child category matches its own descendants",
        deep["id"] in ids_child,
        f"ids={ids_child}",
    )
    check(
        "parent result is a superset of the child result",
        ids_child.issubset(set(ids)),
        f"parent={set(ids)} child={ids_child}",
    )

    # Filtering by the grandchild must be strictly narrower than filtering by its
    # parent: a descendant expands downwards, never upwards.
    r = await _public(client, category=grandchild["id"], size=100)
    grandchild_ids = set(s["id"] for s in r.json()["data"])
    check(
        "grandchild category includes a service tagged with the grandchild",
        deep["id"] in grandchild_ids,
        f"ids={grandchild_ids}",
    )
    check(
        "grandchild filter is a subset of the parent filter (descendants only, never upwards)",
        grandchild_ids.issubset(ids),
        f"parent={ids} grandchild={grandchild_ids}",
    )
    check(
        "grandchild filter excludes a service tagged only with the parent",
        secondary_only["id"] in ids
        and secondary_only["id"] not in grandchild_ids,
        f"parent={ids} grandchild={grandchild_ids}",
    )

    r = await _public(client, category=other["id"])
    check(
        "secondary category is searchable",
        secondary_only["id"] in [s["id"] for s in r.json()["data"]],
        f"ids={[s['id'] for s in r.json()['data']]}",
    )

    # ---- category ANY semantics
    r = await _public(client, category=[other["id"], grandchild["id"]])
    ids = set(s["id"] for s in r.json()["data"])
    check(
        "multiple categories use ANY semantics",
        deep["id"] in ids and secondary_only["id"] in ids,
        f"ids={ids}",
    )

    # a service tagged with two requested categories must not be duplicated
    multi = await _make_service(
        client, headers, "ZZ Multi Tagged",
        status=ServiceStatus.published.value,
        categories=[
            {"category_id": other["id"], "is_primary": True},
            {"category_id": grandchild["id"], "is_primary": False},
        ],
    )
    created["services"].append(multi["id"])
    r = await _public(client, category=[other["id"], grandchild["id"]], size=100)
    matched = [s["id"] for s in r.json()["data"]]
    check(
        "multi-tagged service appears exactly once",
        matched.count(multi["id"]) == 1,
        f"count={matched.count(multi['id'])}",
    )
    check(
        "count and page agree for multi-tagged services",
        r.json()["meta"]["total"] == len(matched),
        f"total={r.json()['meta']['total']} len={len(matched)}",
    )

    # ---- q searches public fields only
    r = await _public(client, q="kabab")
    check("q matches name", deep["id"] in [s["id"] for s in r.json()["data"]], "")
    r = await _public(client, q="zz-kabab")
    check(
        "q matches category slug",
        deep["id"] in [s["id"] for s in r.json()["data"]],
        f"n={len(r.json()['data'])}",
    )
    # q reaches category name and slug through the category LINKAGE, which is a
    # different predicate from the service's own columns. Asserted on `deep`,
    # whose PRIMARY category is the grandchild "ZZ Kabab" (slug zz-kabab) and
    # whose ancestors are the ones being searched for.
    r = await _public(client, q="Kabab")
    check(
        "q matches a word from the assigned category name",
        deep["id"] in [s["id"] for s in r.json()["data"]],
        f"n={len(r.json()['data'])}",
    )
    r = await _public(client, q="zz-kabab")
    check(
        "q matches the assigned category slug",
        deep["id"] in [s["id"] for s in r.json()["data"]],
        f"n={len(r.json()['data'])}",
    )
    # A service is matched by its OWN assigned categories, not by an ancestor's
    # name: `deep` carries the grandchild link, so an ancestor's slug must not
    # match it. This documents that q does not silently expand the category tree
    # the way the category filter does.
    r = await _public(client, q="zz-restaurants")
    check(
        "q does not expand the category tree the way the category filter does",
        deep["id"] not in [s["id"] for s in r.json()["data"]],
        f"n={len(r.json()['data'])}",
    )
    # Multi-word search: every word must appear somewhere in the searched set.
    r = await _public(client, q="ZZ Kabab")
    check(
        "multi-word q matches when both words are present",
        deep["id"] in [s["id"] for s in r.json()["data"]],
        f"n={len(r.json()['data'])}",
    )
    r = await _public(client, q="Kabab Nonexistentword")
    check(
        "multi-word q requires every word to match",
        deep["id"] not in [s["id"] for s in r.json()["data"]],
        f"n={len(r.json()['data'])}",
    )

    # q must NOT match internal/provenance/owner data
    prov = await _make_service(
        client, headers, "ZZ Provenance Probe",
        status=ServiceStatus.published.value,
        source="zzsecretatlas", external_id="zz-secret-id",
        categories=[{"category_id": other["id"], "is_primary": True}],
    )
    created["services"].append(prov["id"])
    r = await _public(client, q="zzsecretatlas")
    check("q does not search source", len(r.json()["data"]) == 0, f"n={len(r.json()['data'])}")
    r = await _public(client, q="zz-secret-id")
    check("q does not search external_id", len(r.json()["data"]) == 0, f"n={len(r.json()['data'])}")

    # ---- unsupported filters / operators are rejected, not ignored
    await _assert_public_rejects(client, headers, "unknown query parameter rejected", "nonexistent", "x")
    await _assert_public_rejects(client, headers, "public cannot filter by status", "status", "published")
    await _assert_public_rejects(client, headers, "public cannot filter by owner", "owner_user_id", "1")
    await _assert_public_rejects(client, headers, "public cannot filter by source", "source", "x")
    await _assert_public_rejects(client, headers, "public cannot filter by description", "description", "x")
    r = await _public(client, sort="name_asc")
    check("supported sort accepted", r.status_code == 200, f"status={r.status_code}")
    r = await _public(client, sort="owner_user_id")
    check("column name as sort rejected", r.status_code == 422, f"status={r.status_code}")
    r = await _public(client, sort="; DROP TABLE services")
    check("hostile sort rejected", r.status_code == 422, f"status={r.status_code}")
    r = await _public(client, size=500)
    check("oversized page rejected", r.status_code == 422, f"status={r.status_code}")

    # ---- deterministic pagination
    r1 = await _public(client, size=2, sort="name_asc", page=1)
    r2 = await _public(client, size=2, sort="name_asc", page=2)
    ids1 = [s["id"] for s in r1.json()["data"]]
    ids2 = [s["id"] for s in r2.json()["data"]]
    check("paging returns distinct pages", not set(ids1) & set(ids2), f"p1={ids1} p2={ids2}")
    r_again = await _public(client, size=2, sort="name_asc", page=1)
    check(
        "paging is stable across identical requests",
        [s["id"] for s in r_again.json()["data"]] == ids1,
        "",
    )

    # ---- LIKE wildcard injection is escaped
    r = await _public(client, q="%")
    check("bare % in q does not match everything", len(r.json()["data"]) == 0, f"n={len(r.json()['data'])}")


# ================================================================== facets


async def _test_facets(client, created):
    print("--- location facets ---")

    r = await client.get(f"{PUBLIC_PREFIX}/services/locations/")
    check("facets endpoint returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    payload = r.json()["data"]

    by_country = {entry["country_code"]: entry for entry in payload}
    check("facets include DE", "DE" in by_country, f"countries={sorted(k for k in by_country if k)}")
    check("facets include non-German countries", "NL" in by_country, f"countries={sorted(k for k in by_country if k)}")

    de_states = {entry["state"]: entry for entry in by_country.get("DE", {}).get("states", [])}
    check("DE facet has a Berlin state node", "Berlin" in de_states, f"states={sorted(k for k in de_states if k)}")
    if "Berlin" in de_states:
        cities = {c["city"]: c for c in de_states["Berlin"]["cities"]}
        check("Berlin state lists the Berlin city", "Berlin" in cities, f"cities={sorted(cities)}")
        check("city carries a count", cities.get("Berlin", {}).get("count", 0) > 0, f"{cities.get('Berlin')}")

    check("facets nest country -> state -> city", "states" in by_country.get("DE", {}), "")

    # only published services are reflected
    async with AsyncSessionLocal() as session:
        published_cities = (
            await session.execute(
                text("select distinct city from services where status='published' and city is not null")
            )
        ).fetchall()
    facet_cities = set()
    for country in payload:
        for state in country.get("states", []):
            for city in state.get("cities", []):
                facet_cities.add(city["city"])
    check(
        "facets reflect published data only",
        set(c[0] for c in published_cities) == facet_cities,
        f"published={sorted(c[0] for c in published_cities)} facets={sorted(facet_cities)}",
    )


# ================================================== legacy user security


async def _test_legacy_user_security():
    print("--- legacy user filter security ---")

    from app.modules.admin.users_management.filters.user_filter import UserFilter
    from app.modules.admin.users_management.schemas.get_user import FullUserResponse

    check(
        "password no longer in admin response schema",
        "password" not in FullUserResponse.model_fields,
        "",
    )

    for name in ("password", "password__ilike", "password__isnull"):
        check(f"{name} filter removed", name not in UserFilter.model_fields, "")

    # invalid sort must not raise
    try:
        f = UserFilter(order_by="nonexistent_column")
        check("invalid sort is rejected at validation", False, "no error raised")
    except Exception:
        check("invalid sort is rejected at validation", True, "")

    # Previously `?order_by=metadata` passed the library's hasattr() check and
    # then raised AttributeError inside sort(), producing an HTTP 500. The
    # validator must now reject it while constructing the filter, i.e. as a 422.
    from sqlalchemy import select

    from app.models.user import User

    rejected = []
    for candidate in ("metadata", "registry", "save", "notacolumn", "privacy_settings"):
        try:
            UserFilter(order_by=candidate)
            rejected.append(f"{candidate} was accepted")
        except Exception:
            pass
    check(
        "non-column sort values are rejected at validation",
        not rejected,
        "; ".join(rejected),
    )

    # And a legitimate column still works, so the allow-list is not simply empty.
    try:
        check(
            "real column still orderable",
            UserFilter(order_by="-counter").order_by == ["-counter"],
            "",
        )
    except Exception as exc:
        check("real column still orderable", False, f"{type(exc).__name__}: {exc}")


async def main() -> None:
    headers = await _headers()
    created: dict = {"services": [], "categories": []}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
        try:
            de, non_german = await _test_location_model(client, headers, created)
            await _test_search(client, headers, created, non_german)
            await _test_facets(client, created)
        finally:
            async with AsyncSessionLocal() as session:
                if created["services"]:
                    ids = created["services"]
                    await session.execute(
                        delete(ServiceContact).where(ServiceContact.service_id.in_(ids))
                    )
                    await session.execute(
                        delete(ServiceCategory).where(ServiceCategory.service_id.in_(ids))
                    )
                    await session.execute(delete(Service).where(Service.id.in_(ids)))
                if created["categories"]:
                    await session.execute(
                        delete(Category).where(Category.id.in_(created["categories"]))
                    )
                targets = [str(x) for x in (created["services"] + created["categories"])]
                if targets:
                    await session.execute(
                        delete(AdminAuditLog).where(AdminAuditLog.target_id.in_(targets))
                    )
                await session.commit()
                print(
                    "cleanup: removed",
                    len(created["services"]),
                    "service(s),",
                    len(created["categories"]),
                    "category/categories, and their audit rows",
                )
            await engine.dispose()

    await _test_legacy_user_security()

    if failures:
        raise AssertionError(f"{len(failures)} check(s) failed: {failures}")
    print("PASS: international location, search, facets and legacy-user security")


if __name__ == "__main__":
    asyncio.run(main())