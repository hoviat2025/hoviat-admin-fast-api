"""Repair only unchanged imported profile text and unwanted imported contacts.

Default is a read-only plan; --apply targets the guarded local database only.
Original extraction, rejected contacts and raw source stay in the import folder.
Administrator-edited descriptions are left alone and recorded for manual review.
"""

import argparse
import asyncio
from datetime import datetime, timezone
from ipaddress import ip_address
import json
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from import_hamvatan_de import DATA, FILES, SOURCE, description, load_entries, settings


def legacy_description(entry):
    metadata = entry.get("metadata", entry)
    parts = [entry["description"].strip()]
    aliases = [name for name in metadata.get("aliases", []) if name not in parts[0]]
    if aliases:
        parts.append("نام‌های دیگر در منبع: " + " / ".join(aliases))
    date = metadata["source_message_date"][:10]
    parts.append(f"اطلاعات برگرفته از منبع در تاریخ {date} است؛ صحت و به‌روز بودن آن مستقلاً بررسی نشده است.")
    return "\n\n".join(parts)


async def run(apply=False):
    entries = load_entries()
    legacy = {entry["external_id"]: entry for entry in json.loads((DATA / "original-extraction.json").read_text(encoding="utf-8"))}
    url = make_url(settings.DATABASE_URL)
    if (url.host, url.port, url.database) != ("127.0.0.1", 5433, "hoviat_service_dev") or not settings.DISABLE_BACKGROUND_WORKERS:
        raise RuntimeError("Expected local development database with workers disabled")
    connection = await asyncpg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False), timeout=5)
    report = {"changed_at": datetime.now(timezone.utc).isoformat(), "applied": apply, "entries": []}
    try:
        database, address = await connection.fetchrow("SELECT current_database(),inet_server_addr()::text")
        if database != "hoviat_service_dev" or not ip_address(address.split("/")[0]).is_loopback:
            raise RuntimeError("Local database identity guard failed")
        async with connection.transaction():
            for entry in entries:
                row = await connection.fetchrow("SELECT id,name,description,status::text FROM public.services WHERE source=$1 AND external_id=$2 FOR UPDATE", SOURCE, entry["external_id"])
                if row is None:
                    report["entries"].append({"external_id": entry["external_id"], "operation": "missing"})
                    continue
                original = legacy[entry["external_id"]]
                item = {"external_id": entry["external_id"], "service_id": row["id"], "description": "unchanged", "removed_contact_ids": []}
                desired = description(entry)
                if row["description"] == legacy_description(original):
                    item["description"] = "replace_imported_text"
                    if apply:
                        await connection.execute("UPDATE public.services SET description=$2,updated_at=clock_timestamp() WHERE id=$1", row["id"], desired)
                elif row["description"] != desired:
                    item["description"] = "preserved_admin_edit"
                bad_values = {c["value"] for c in original["contacts"] if c.get("platform") == "google_maps" or entry["external_id"] == "1571:10"}
                source_url = original.get("metadata", original)["source_message_url"]
                bad_values.add(source_url)
                contacts = await connection.fetch("SELECT id,title,type::text,value,platform FROM public.service_contacts WHERE service_id=$1 AND value=ANY($2::text[])", row["id"], list(bad_values))
                # Compare imported signatures too: an administrator's replacement title/platform is preserved.
                signatures = {(c["title"], c["type"], c["value"], c.get("platform")) for c in original["contacts"]}
                signatures.add(("منبع اطلاعات", "url", source_url, "telegram"))
                imported_contacts = [c for c in contacts if (c["title"], c["type"], c["value"], c["platform"]) in signatures]
                item["removed_contacts"] = [dict(c) for c in imported_contacts]
                item["removed_contact_ids"] = [c["id"] for c in imported_contacts]
                if apply and imported_contacts:
                    await connection.execute("DELETE FROM public.service_contacts WHERE id=ANY($1::bigint[])", item["removed_contact_ids"])
                if entry.get("status") == "draft" and row["name"] == original["name"] and row["description"] in {legacy_description(original), desired}:
                    item["status"] = "draft"
                    if apply:
                        await connection.execute("UPDATE public.services SET status='draft',updated_at=clock_timestamp() WHERE id=$1", row["id"])
                report["entries"].append(item)
            if apply:
                await connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        if apply:
            # Keep first repair evidence; a second run must not erase the list of removed contacts.
            target = DATA / "profile-repair-report.json"
            if not target.exists():
                target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"applied": apply, "profiles_rewritten": sum(e.get("description") == "replace_imported_text" for e in report["entries"]), "contacts_removed": sum(len(e.get("removed_contact_ids", [])) for e in report["entries"]), "admin_text_preserved": sum(e.get("description") == "preserved_admin_edit" for e in report["entries"]), "pending_entries": [e["external_id"] for e in report["entries"] if e.get("status") == "draft"]}, ensure_ascii=False))
    finally:
        await connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args().apply))
