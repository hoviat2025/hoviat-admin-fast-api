r"""Import the reviewed 35 source entries into the guarded LOCAL directory.

Preview (no database writes):
  .venv\Scripts\python.exe -X utf8 scripts/database/import_hamvatan_de.py
Apply:
  .venv\Scripts\python.exe -X utf8 scripts/database/import_hamvatan_de.py --apply

The source snapshot and reviewed extraction live together under data/imports/.
No scraping, verification, user assignment, media download, job or API call is
performed. Existing source+entry keys are skipped, preserving later admin edits.
Do not use message IDs alone: each post contains several independent entries.
"""

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
from ipaddress import ip_address
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import asyncpg
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.core.config import settings

DATA = ROOT / "data/imports/hamvatan-de-20261019"
SOURCE = "telegram:HamvatanDE"
FILES = ("medical.json", "gyms.json", "swimming.json")
EXPECTED_POSTS = {1352: 4, 1354: 4, 1362: 2, 1569: 15, 1571: 10}
FLAGS = ("persian_owned", "persian_provider", "persian_language", "persian_service")
# Only categories the actual supplied material needs. All retain two levels.
NEW_CATEGORIES = (
    ("sports-wellbeing", "ورزش و تندرستی", ()),
    ("fitness", "باشگاه و تناسب اندام", ("sports-wellbeing",)),
    ("swimming", "شنا و آموزش شنا", ("sports-wellbeing", "education")),
    ("sports-association", "انجمن‌ها و باشگاه‌های ورزشی", ("sports-wellbeing", "events-culture")),
    ("neuropsychiatry", "مغز و اعصاب و روان‌پزشکی", ("healthcare",)),
)


def http_url(value):
    try:
        parsed = urlsplit(value)
        parsed.port
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except (TypeError, ValueError):
        return False


def load_entries():
    entries = []
    for filename in FILES:
        for raw in json.loads((DATA / filename).read_text(encoding="utf-8-sig")):
            entry = dict(raw)
            metadata = dict(raw.get("metadata") or {})
            for field in ("source_message_id", "source_message_url", "source_message_date", "raw_entry", "aliases", "review_notes"):
                if field in raw:
                    metadata[field] = raw[field]
            entry["metadata"] = metadata
            entry_id = entry["external_id"]
            post_id, ordinal = (int(part) for part in entry_id.split(":"))
            if post_id != metadata["source_message_id"] or not 1 <= ordinal <= EXPECTED_POSTS[post_id]:
                raise ValueError(f"Unexpected source identity: {entry_id}")
            if metadata["source_message_url"] != f"https://t.me/HamvatanDE/{post_id}" or not metadata["raw_entry"].strip():
                raise ValueError(f"Missing source evidence: {entry_id}")
            datetime.fromisoformat(metadata["source_message_date"])
            if not entry["name"].strip() or len(entry["name"]) > 300:
                raise ValueError(f"Invalid listing name: {entry_id}")
            if entry["country_code"] != "DE" or entry["city"] not in {"Berlin", "Bremen"} or entry["state"] != entry["city"]:
                raise ValueError(f"Review location: {entry_id}")
            for field in FLAGS:
                if entry.get(field) is not None and type(entry[field]) is not bool:
                    raise ValueError(f"Invalid relevance answer: {entry_id}/{field}")
            for contact in entry["contacts"]:
                if contact["type"] not in {"phone", "email", "url", "username", "other"} or not contact["title"].strip() or not contact["value"].strip():
                    raise ValueError(f"Invalid contact: {entry_id}")
                if contact["type"] == "url" and not http_url(contact["value"]):
                    raise ValueError(f"Invalid contact URL: {entry_id}")
                if contact["type"] == "phone" and not re.fullmatch(r"\+49[0-9]{5,15}", contact["value"]):
                    raise ValueError(f"Review phone normalization: {entry_id}")
            entries.append(entry)
    if len(entries) != 35 or len({entry["external_id"] for entry in entries}) != 35:
        raise ValueError("Expected exactly 35 distinct source entries")
    if Counter(entry["metadata"]["source_message_id"] for entry in entries) != Counter(EXPECTED_POSTS):
        raise ValueError("Post/entry coverage differs from the raw source")
    return entries


async def ensure_categories(connection, needed):
    created = []
    rows = await connection.fetch("SELECT id,slug,parent_id,is_active FROM public.categories")
    by_slug = {row["slug"]: dict(row) for row in rows}
    for slug, name, parents in NEW_CATEGORIES:
        if slug in by_slug:
            continue  # Never rename/move/reactivate an administrator's category.
        parent_ids = [by_slug[parent]["id"] for parent in parents]
        row = await connection.fetchrow("""
            INSERT INTO public.categories(name,slug,parent_id,is_active,display_order)
            VALUES($1,$2,$3,true,1000) RETURNING id,slug,parent_id,is_active
        """, name, slug, parent_ids[0] if parent_ids else None)
        by_slug[slug] = dict(row)
        if parent_ids:
            await connection.executemany(
                "INSERT INTO public.category_parents(category_id,parent_id) VALUES($1,$2)",
                [(row["id"], parent) for parent in parent_ids],
            )
        created.append(slug)
    for slug in needed:
        if slug not in by_slug or not by_slug[slug]["is_active"] or by_slug[slug]["parent_id"] is None:
            raise ValueError(f"An active subcategory is required before publishing: {slug}")
    return by_slug, created


def description(entry):
    # Provenance and aliases stay in the internal extraction/report, not the profile.
    return entry["description"].strip()


async def run(apply=False):
    entries = load_entries()
    source_bytes = (DATA / "source.txt").read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    url = make_url(settings.DATABASE_URL)
    if (url.host, url.port, url.database) != ("127.0.0.1", 5433, "hoviat_service_dev") or not settings.DISABLE_BACKGROUND_WORKERS:
        raise RuntimeError("Refusing import: expected guarded local development database with workers disabled")
    connection = await asyncpg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False), timeout=5)
    report = {
        "source": SOURCE, "source_file_sha256": digest,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "target": "127.0.0.1:5433/hoviat_service_dev", "entries": [],
        "note": "Source-provided claims, not independently verified. Existing records are never overwritten.",
    }
    try:
        name, address = await connection.fetchrow("SELECT current_database(),inet_server_addr()::text")
        if name != "hoviat_service_dev" or not ip_address(address.split("/")[0]).is_loopback:
            raise RuntimeError("Refusing import: database server identity guard failed")
        async with connection.transaction():
            if apply:
                await connection.execute("SELECT pg_advisory_xact_lock(606125019)")
            known = {row["slug"] for row in await connection.fetch("SELECT slug FROM public.categories")}
            missing = [slug for slug, _, _ in NEW_CATEGORIES if slug not in known]
            print("GUARD PASS: local development DB, workers disabled")
            print("New categories:", missing)
            categories, created = await ensure_categories(connection, {entry["category_slug"] for entry in entries}) if apply else ({}, [])
            report["created_categories"] = created
            for entry in entries:
                existing_id = await connection.fetchval(
                    "SELECT id FROM public.services WHERE source=$1 AND external_id=$2", SOURCE, entry["external_id"],
                )
                operation = "skip_existing" if existing_id is not None else "insert"
                service_id = existing_id
                if apply and existing_id is None:
                    service_id = await connection.fetchval("""
                        INSERT INTO public.services(name,description,address,postal_code,city,state,country_code,
                            persian_owned,persian_provider,persian_language,persian_service,status,source,external_id)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'draft',$12,$13) RETURNING id
                    """, entry["name"], description(entry), entry.get("address"), entry.get("postal_code"),
                        entry["city"], entry["state"], "DE", *(entry.get(field) for field in FLAGS), SOURCE, entry["external_id"])
                    await connection.execute("INSERT INTO public.service_categories(service_id,category_id,is_primary) VALUES($1,$2,true)", service_id, categories[entry["category_slug"]]["id"])
                    contacts = list(entry["contacts"])
                    for order, contact in enumerate(contacts):
                        await connection.execute("""
                            INSERT INTO public.service_contacts(service_id,title,type,value,platform,display_order,is_visible)
                            VALUES($1,$2,$3::service_contact_type,$4,$5,$6,$7)
                        """, service_id, contact["title"], contact["type"], contact["value"], contact.get("platform"), order, contact.get("is_visible", True))
                    await connection.execute("UPDATE public.services SET status=$2::service_status,updated_at=clock_timestamp() WHERE id=$1", service_id, entry.get("status", "published"))
                print(f"{operation}: {entry['external_id']} {entry['name']} -> {service_id or '(new)'}")
                report["entries"].append({
                    "external_id": entry["external_id"], "service_id": service_id, "name": entry["name"],
                    "operation": operation, "metadata": entry["metadata"],
                })
            if apply:
                await connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
                ids = [item["service_id"] for item in report["entries"]]
                report["published_count"] = await connection.fetchval(
                    "SELECT count(*) FROM public.services WHERE id=ANY($1::bigint[]) AND status='published'", ids,
                )
        if apply:
            (DATA / "import-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("COMMITTED:", Counter(item["operation"] for item in report["entries"]), "published:", report["published_count"])
            print("Audit:", DATA / "import-report.json")
        else:
            print("PLAN ONLY: no database writes. Pass --apply after reviewing the extraction.")
    finally:
        await connection.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
