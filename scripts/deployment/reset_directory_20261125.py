"""Explicit one-time directory reset. Never called by imports or migrations.

On the VPS, inspect first:
  sudo python3 scripts/deployment/reset_directory_20261125.py --database hoviat_sns_stage_20261021
Apply only after reviewing counts; --help describes the confirmation.
Uses PostgreSQL CLI tools, not application startup, workers, Telegram or R2.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile


TABLES = ("services", "categories", "category_parents", "service_categories", "service_contacts", "service_bookmarks")
COUNTS = "\n".join(f"SELECT '{name}' AS directory_table, count(*) AS rows FROM public.{name};" for name in TABLES)
RESET_SQL = """
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SELECT pg_advisory_xact_lock(606125199);
LOCK TABLE public.services, public.categories, public.category_parents,
    public.service_categories, public.service_contacts, public.service_bookmarks
    IN ACCESS EXCLUSIVE MODE;
DELETE FROM public.services;
DELETE FROM public.category_parents;
DELETE FROM public.categories WHERE parent_id IS NOT NULL;
DELETE FROM public.categories;
COMMIT;
"""


def main():
    parser = argparse.ArgumentParser(description="Preview or explicitly reset only directory businesses/categories and their dependent links/bookmarks. Preserves users, locations, audit records, Telegram state and R2 objects.")
    parser.add_argument("--database", required=True, choices=("hoviat", "hoviat_sns_stage_20261021"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", help='For apply, exactly: "EMPTY DIRECTORY IN <database>"')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run with sudo; database access uses the local postgres account.")
    if args.apply and args.confirm != f"EMPTY DIRECTORY IN {args.database}":
        parser.error("Apply requires the exact --confirm phrase for the selected database.")
    command = ["sudo", "-u", "postgres", "psql", "-X", "--host=/var/run/postgresql", "--port=5432", "-d", args.database, "-v", "ON_ERROR_STOP=1"]
    subprocess.run(command, input="BEGIN READ ONLY;\nSET LOCAL statement_timeout = '15s';\n" + COUNTS + "\nCOMMIT;", text=True, check=True)
    if not args.apply:
        print("PREVIEW ONLY: nothing deleted. Apply requires --apply and --confirm.")
        return

    # Retain a full private database snapshot before the single delete transaction.
    postgres = pwd.getpwnam("postgres")
    os.umask(0o077)
    backup = Path(tempfile.mkdtemp(prefix="directory-reset-20261125-", dir="/var/lib/postgresql"))
    os.chown(backup, postgres.pw_uid, postgres.pw_gid)
    subprocess.run(["sudo", "-u", "postgres", "pg_dump", "--host=/var/run/postgresql", "--port=5432", "--format=custom", "--dbname", args.database,
                    "--file", str(backup / "before-reset.dump")], check=True)
    print("Private database backup:", backup / "before-reset.dump", flush=True)
    subprocess.run(command, input=RESET_SQL, text=True, check=True)
    (backup / "reset-completed.json").write_text(json.dumps({"database": args.database, "tables": TABLES}), encoding="utf-8")
    subprocess.run(command, input="BEGIN READ ONLY;\n" + COUNTS + "\nCOMMIT;", text=True, check=True)
    print("Directory reset complete. No user/location tables, services, Telegram or storage settings were changed.")


if __name__ == "__main__":
    main()
