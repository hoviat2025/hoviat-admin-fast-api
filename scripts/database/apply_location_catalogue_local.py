"""Apply migration 21 to the local development database only; preview by default."""
import argparse
import asyncio
from ipaddress import ip_address
from pathlib import Path
import sys

import asyncpg
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.core.config import settings


async def main(apply=False):
    url = make_url(settings.DATABASE_URL)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or url.database != "hoviat_service_dev":
        raise RuntimeError("This helper only supports the local hoviat_service_dev database")
    db = await asyncpg.connect(user=url.username, password=url.password, host=url.host,
                              port=url.port or 5432, database=url.database)
    try:
        identity = await db.fetchrow("SELECT current_database() name, host(inet_server_addr()) host")
        if identity["name"] != "hoviat_service_dev" or not ip_address(identity["host"]).is_loopback:
            raise RuntimeError("Local database identity check failed")
        print("Locations:", [dict(r) for r in await db.fetch(
            "SELECT country_code,state,city,count(*) total FROM services GROUP BY 1,2,3 ORDER BY 1,2,3")])
        print("Root assignments:", [dict(r) for r in await db.fetch(
            "SELECT sc.service_id,c.name,c.slug,sc.is_primary FROM service_categories sc "
            "JOIN categories c ON c.id=sc.category_id WHERE c.parent_id IS NULL")])
        if apply:
            await db.execute((ROOT / "scripts/database/20261020_21_canonical_cities_and_leaf_categories.sql").read_text(encoding="utf-8"))
            print("Migration 21 committed.")
            print("Defined cities:", await db.fetchval("SELECT count(*) FROM cities"))
            print("Linked listings:", await db.fetchval("SELECT count(*) FROM services WHERE city_id IS NOT NULL"))
    finally:
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
