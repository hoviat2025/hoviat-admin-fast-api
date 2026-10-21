r"""Guarded local-only curated taxonomy. Default is a read-only plan; --apply writes.

Run from repository root after migrations 19/20:
  rtk proxy .venv\Scripts\python.exe scripts/database/seed_local_business_taxonomy.py
  rtk proxy .venv\Scripts\python.exe scripts/database/seed_local_business_taxonomy.py --apply

Only explicit slug aliases or normalized exact Persian names are consolidated.
Every service assignment and primary flag is checked before commit.
"""

import argparse
import asyncio
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
import re
import sys
import unicodedata

import asyncpg
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.config import settings


@dataclass(frozen=True)
class CategorySeed:
    slug: str
    name: str
    parents: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    names: tuple[str, ...] = ()


ROOTS = (
    CategorySeed("food", "غذا و نوشیدنی", aliases=("food-drink", "food-and-drink"), names=("غذا",)),
    CategorySeed("healthcare", "سلامت و درمان", aliases=("health", "health-wellbeing"), names=("سلامت",)),
    CategorySeed("professional-services", "حقوق، امور اداری و مالی", aliases=("legal-financial",), names=("خدمات حرفه‌ای",)),
    CategorySeed("home-property", "خانه و املاک", aliases=("home-and-property",), names=("خانه و ساختمان",)),
    CategorySeed("beauty", "زیبایی و مراقبت شخصی", aliases=("beauty-personal-care",), names=("زیبایی",)),
    CategorySeed("education", "آموزش و زبان", aliases=("education-language",), names=("آموزش",)),
    CategorySeed("events-culture", "رویداد، هنر و فرهنگ", aliases=("events-and-culture",), names=("رویداد و فرهنگ",)),
    CategorySeed("shopping-daily", "خرید و خدمات روزمره", aliases=("shopping-and-daily-services",), names=("خرید و خدمات روزانه",)),
)

CHILDREN = (
    CategorySeed("restaurant", "رستوران", ("food",), ("restaurants",), ("رستوران‌ها",)),
    CategorySeed("cafe", "کافه", ("food",), ("cafes", "coffee-shop"), ("کافی‌شاپ",)),
    CategorySeed("catering", "تهیه غذا و کترینگ", ("food", "events-culture"), (), ("کیترینگ", "کترینگ", "تهیه غذا")),
    CategorySeed("bakery", "نانوایی و شیرینی‌فروشی", ("food",), ("bakeries", "bakeries-confectionery"), ("نانوایی",)),
    CategorySeed("grocery-store", "فروشگاه مواد غذایی", ("food", "shopping-daily"), ("grocery", "supermarket"), ("خواربارفروشی", "سوپرمارکت")),
    CategorySeed("doctor", "پزشک و مطب", ("healthcare",), ("doctors", "physician"), ("پزشک",)),
    CategorySeed("dentist", "دندان‌پزشکی", ("healthcare",), ("dentists", "dentistry"), ("دندانپزشک", "دندانپزشکی")),
    CategorySeed("clinic", "کلینیک درمانی", ("healthcare",), ("clinics",), ("کلینیک",)),
    CategorySeed("mental-health", "روان‌شناسی و مشاوره", ("healthcare",), ("psychotherapy", "psychology"), ("روانشناسی",)),
    CategorySeed("physiotherapy", "فیزیوتراپی", ("healthcare",), ("physical-therapy",)),
    CategorySeed("lawyer", "وکیل و مشاوره حقوقی", ("professional-services",), ("lawyers",), ("وکیل",)),
    CategorySeed("accountant", "حسابداری و مالیات", ("professional-services",), ("accountants", "accounting", "tax-advisory"), ("حسابدار", "حسابداری")),
    CategorySeed("insurance", "بیمه", ("professional-services",), ("insurance-services",)),
    CategorySeed("translator", "ترجمه و مترجمی", ("professional-services", "education"), ("translation", "translation-interpreting"), ("مترجم", "ترجمه")),
    CategorySeed("real-estate", "مشاور املاک", ("home-property",), ("real-estate-agency",), ("املاک",)),
    CategorySeed("home-repair", "تعمیرات و بازسازی خانه", ("home-property",), ("repairs-renovation",), ("بازسازی خانه",)),
    CategorySeed("cleaning", "نظافت", ("home-property",), ("cleaning-services",)),
    CategorySeed("moving", "حمل‌ونقل و اسباب‌کشی", ("home-property", "shopping-daily"), ("moving-services",), ("اسباب‌کشی",)),
    CategorySeed("hairdresser", "آرایشگاه", ("beauty",), ("hair-salons", "hairdresser-services"), ("آرایشگر",)),
    CategorySeed("beauty-clinic", "پوست و زیبایی", ("beauty", "healthcare"), ("skin-beauty",), ("کلینیک زیبایی",)),
    CategorySeed("language-school", "آموزش زبان", ("education",), ("language-courses",)),
    CategorySeed("tutoring", "تدریس خصوصی", ("education",), ("private-tutoring",)),
    CategorySeed("driving-school", "آموزش رانندگی", ("education", "shopping-daily"), ("driving-schools",)),
    CategorySeed("music-art-education", "آموزش موسیقی و هنر", ("education", "events-culture"), ("music-art-lessons",)),
    CategorySeed("event-planning", "برگزاری مراسم", ("events-culture",), ("event-services",)),
    CategorySeed("photography", "عکاسی و فیلم‌برداری", ("events-culture", "shopping-daily"), ("photo-video",), ("عکاسی",)),
    CategorySeed("travel-agency", "گردشگری و آژانس سفر", ("events-culture",), ("travel-tourism",), ("آژانس مسافرتی",)),
    CategorySeed("car-services", "خدمات خودرو", ("shopping-daily",), ("automotive", "automotive-services"), ("خودرو",)),
    CategorySeed("repair-service", "تعمیرات خودرو", ("shopping-daily",), ("car-repair", "auto-repair")),
    CategorySeed("retail-store", "فروشگاه و خرید", ("shopping-daily",), ("retail-shops",)),
    CategorySeed("tailoring", "خیاطی و تعمیر لباس", ("shopping-daily",), ("tailor",), ("خیاطی",)),
    CategorySeed("computer-mobile-repair", "تعمیر رایانه و موبایل", ("shopping-daily",), ("computer-repair", "mobile-repair")),
)
TAXONOMY = ROOTS + CHILDREN


def fold_name(value):
    normalized = unicodedata.normalize("NFKC", value).translate(str.maketrans({"ي": "ی", "ك": "ک"}))
    return re.sub(r"[\s\u200c\u200dـ،,\-_/]+", "", normalized).casefold()


def matching_plan(rows):
    claimed = {}
    plan = []
    for spec in TAXONOMY:
        names = {fold_name(name) for name in (spec.name, *spec.names)}
        candidates = [row for row in rows if row["slug"] in (spec.slug, *spec.aliases) or fold_name(row["name"]) in names]
        candidates.sort(key=lambda row: (
            row["slug"] != spec.slug,
            (spec.aliases.index(row["slug"]) if row["slug"] in spec.aliases else len(spec.aliases)),
            row["id"],
        ))
        for row in candidates:
            if row["id"] in claimed:
                raise RuntimeError("Ambiguous taxonomy alias; review seed definitions before applying")
            claimed[row["id"]] = spec.slug
        plan.append((spec, candidates))
    return plan


async def merge_duplicate(connection, old_id, target_id):
    moved = await connection.fetch("""
        WITH moved AS (
            DELETE FROM public.service_categories WHERE category_id=$1 RETURNING service_id,is_primary
        )
        INSERT INTO public.service_categories (service_id,category_id,is_primary)
        SELECT service_id,$2,is_primary FROM moved
        ON CONFLICT (service_id,category_id) DO UPDATE
        SET is_primary=service_categories.is_primary OR EXCLUDED.is_primary
        RETURNING service_id
    """, old_id, target_id)
    # Clear a target's temporary relationship to its duplicate before rewiring,
    # so the existing non-self-parent CHECK is never violated during the merge.
    await connection.execute("UPDATE public.categories SET parent_id=NULL WHERE id=$1 AND parent_id=$2", target_id, old_id)
    await connection.execute("UPDATE public.categories SET parent_id=$2,updated_at=clock_timestamp() WHERE parent_id=$1 AND id<>$2", old_id, target_id)
    await connection.execute("""
        INSERT INTO public.category_parents(category_id,parent_id)
        SELECT category_id,$2 FROM public.category_parents WHERE parent_id=$1 AND category_id<>$2
        ON CONFLICT DO NOTHING
    """, old_id, target_id)
    await connection.execute("""
        INSERT INTO public.category_parents(category_id,parent_id)
        SELECT $2,parent_id FROM public.category_parents WHERE category_id=$1 AND parent_id<>$2
        ON CONFLICT DO NOTHING
    """, old_id, target_id)
    await connection.execute("DELETE FROM public.category_parents WHERE category_id=$1 OR parent_id=$1", old_id)
    await connection.execute("DELETE FROM public.categories WHERE id=$1", old_id)
    return {row["service_id"] for row in moved}


async def apply_seed(connection, plan):
    before = await connection.fetch("SELECT service_id,category_id,is_primary FROM public.service_categories")
    canonical_ids, mapping = {}, {}
    for order, (spec, candidates) in enumerate(plan):
        if candidates:
            target_id = candidates[0]["id"]
            await connection.execute("""
                UPDATE public.categories SET name=$2,slug=$3,display_order=$4,is_active=true,updated_at=clock_timestamp()
                WHERE id=$1 AND (name IS DISTINCT FROM $2 OR slug IS DISTINCT FROM $3 OR display_order IS DISTINCT FROM $4 OR NOT is_active)
            """, target_id, spec.name, spec.slug, (order + 1) * 10)
        else:
            target_id = await connection.fetchval("""
                INSERT INTO public.categories(name,slug,display_order,is_active)
                VALUES($1,$2,$3,true) RETURNING id
            """, spec.name, spec.slug, (order + 1) * 10)
        canonical_ids[spec.slug] = target_id
        mapping.update({row["id"]: target_id for row in candidates})

    affected_services = set()
    for spec, candidates in plan:
        target_id = canonical_ids[spec.slug]
        for duplicate in candidates[1:]:
            old_id = duplicate["id"]
            affected_services |= await merge_duplicate(connection, old_id, target_id)
            print(f"MERGE category {old_id} -> {target_id} ({spec.slug})")

    rows = {row["id"]: row for row in await connection.fetch("SELECT id,parent_id FROM public.categories")}
    current = {row_id: set() for row_id in rows}
    for edge in await connection.fetch("SELECT category_id,parent_id FROM public.category_parents"):
        current[edge["category_id"]].add(edge["parent_id"])
    for row_id, row in rows.items():
        if row["parent_id"] is not None:
            current[row_id].add(row["parent_id"])
    curated = {canonical_ids[spec.slug]: [canonical_ids[slug] for slug in spec.parents] for spec in TAXONOMY}

    def roots_for(parent_id, path=frozenset()):
        if parent_id in path:
            raise RuntimeError("Unexpected category cycle; seed aborted")
        if parent_id in curated:
            parents = curated[parent_id]
        else:
            parents = current[parent_id]
        if not parents:
            return {parent_id}
        return set().union(*(roots_for(value, path | {parent_id}) for value in parents))

    for row_id, row in rows.items():
        if row_id in curated and not curated[row_id]:
            parents = set()
        else:
            parents = set(curated.get(row_id, ()))
            for parent_id in current[row_id]:
                parents |= roots_for(parent_id)
            parents.discard(row_id)
        primary = row["parent_id"] if row["parent_id"] in parents else (
            next((value for value in curated.get(row_id, ()) if value in parents), min(parents) if parents else None)
        )
        if parents != current[row_id] or primary != row["parent_id"]:
            await connection.execute("UPDATE public.categories SET parent_id=$2,updated_at=clock_timestamp() WHERE id=$1", row_id, primary)
            await connection.execute("DELETE FROM public.category_parents WHERE category_id=$1", row_id)
            if parents:
                await connection.executemany(
                    "INSERT INTO public.category_parents(category_id,parent_id) VALUES($1,$2)",
                    [(row_id, value) for value in sorted(parents)],
                )
            print(f"PARENTS category {row_id}: {sorted(parents)}; primary={primary}")

    # Merging IDs must never lose an assignment or change its primary meaning.
    expected = {}
    for row in before:
        key = (row["service_id"], mapping.get(row["category_id"], row["category_id"]))
        expected[key] = expected.get(key, False) or row["is_primary"]
    after = {(row["service_id"], row["category_id"]): row["is_primary"] for row in await connection.fetch("SELECT service_id,category_id,is_primary FROM public.service_categories")}
    if after != expected:
        raise RuntimeError("Assignment preservation check failed; seed rolled back")
    if affected_services:
        await connection.execute("UPDATE public.services SET updated_at=clock_timestamp() WHERE id=ANY($1::bigint[])", sorted(affected_services))
    await connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    print(f"READY: {len(ROOTS)} curated roots, {len(CHILDREN)} curated children; service assignments and primary flags preserved")


async def main(apply=False):
    url = make_url(settings.DATABASE_URL)
    if (url.host, url.port, url.database) != ("127.0.0.1", 5433, "hoviat_service_dev") or not settings.DISABLE_BACKGROUND_WORKERS:
        raise RuntimeError("Refusing any database except loopback:5433/hoviat_service_dev with background workers disabled")
    connection = await asyncpg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False), timeout=5)
    try:
        database, address = await connection.fetchrow("SELECT current_database(),inet_server_addr()::text")
        if database != "hoviat_service_dev" or not ip_address(address.split("/", 1)[0]).is_loopback:
            raise RuntimeError("Server identity guard failed; no changes made")
        if not await connection.fetchval("SELECT to_regclass('public.category_parents')"):
            raise RuntimeError("Apply migration 19 before planning or applying this seed")
        print("GUARD PASS: local hoviat_service_dev with background workers disabled")
        async with connection.transaction():
            if apply:
                await connection.execute("SELECT pg_advisory_xact_lock(606125019)")
                await connection.execute("LOCK TABLE public.services,public.service_categories,public.categories,public.category_parents IN SHARE ROW EXCLUSIVE MODE")
            rows = await connection.fetch("SELECT id,name,slug,parent_id FROM public.categories ORDER BY id")
            plan = matching_plan(rows)
            for spec, candidates in plan:
                action = f"reuse {candidates[0]['id']}" if candidates else "create"
                duplicates = [row["id"] for row in candidates[1:]]
                print(f"PLAN {spec.slug}: {action}; parents={list(spec.parents)}; duplicate_ids={duplicates}")
            if apply:
                await apply_seed(connection, plan)
            else:
                print("PLAN ONLY: no rows changed. Review aliases/mapping, then pass --apply.")
        if apply:
            print("COMMITTED: local taxonomy seed only; no users or business details were changed")
    finally:
        await connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
