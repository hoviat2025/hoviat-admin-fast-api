"""Create fresh isolated staging env files after restore, migrations and deps.

Manual VPS operation only. This script does not start services, change database
rows, or read/copy any existing environment file. Credentials are never printed.
Run with the release backend's .venv/bin/python as its non-root owner.
"""

import asyncio
import getpass
import json
import os
from pathlib import Path
import secrets
import socket
import sys
from urllib.parse import urlsplit

import asyncpg
from sqlalchemy import URL


EXPECTED_HOST = "srv5089629844"
EXPECTED_RELEASE = Path("/home/bardia/apps/sns-staging/releases/20261021-01")
DATABASE = "hoviat_sns_stage_20261021"
ROLE = "hoviat_sns_stage"
DB_HOST = "127.0.0.1"
DB_PORT = 5432
API_ORIGIN = "http://127.0.0.1:18753"


class SetupRefused(Exception):
    pass


def checked_paths() -> tuple[Path, dict[str, Path]]:
    if sys.platform != "linux" or socket.gethostname() != EXPECTED_HOST:
        raise SetupRefused("This script is restricted to the approved staging VPS.")
    if os.geteuid() == 0:
        raise SetupRefused("Run as the non-root release owner, not root.")
    if not sys.stdin.isatty():
        raise SetupRefused("An interactive terminal is required for hidden password input.")
    script = Path(__file__).absolute()
    if script.resolve(strict=True) != script:
        raise SetupRefused("Symlinked script or parent directories are not allowed.")
    backend = script.parents[2]
    release = backend.parent
    if backend.name != "backend" or release != EXPECTED_RELEASE:
        raise SetupRefused("Script must run from a new backend under the staging releases directory.")
    if Path(sys.prefix).absolute() != backend / ".venv":
        raise SetupRefused("Use this release's backend/.venv/bin/python interpreter.")
    directories = {name: release / name for name in ("backend", "consumer", "admin")}
    for directory in directories.values():
        if not directory.is_dir() or directory.resolve(strict=True) != directory:
            raise SetupRefused("All three release directories must exist without symlinks.")
        if directory.stat().st_uid != os.geteuid():
            raise SetupRefused("The current user must own all three release directories.")
        for existing in directory.glob(".env*"):
            if existing.is_symlink() or not existing.name.endswith((".example", ".sample")):
                raise SetupRefused("Existing environment files or symlinks require review before bootstrap.")
    files = {
        "backend": backend / ".env",
        "consumer": directories["consumer"] / ".env.local",
        "admin": directories["admin"] / ".env.production",
    }
    for path in files.values():
        if path.exists() or path.is_symlink():
            raise SetupRefused("An environment target already exists; nothing will be overwritten.")
    return release, files


async def verify_database(password: str) -> None:
    connection = None
    try:
        connection = await asyncpg.connect(
            host=DB_HOST, port=DB_PORT, database=DATABASE,
            user=ROLE, password=password, timeout=10, command_timeout=10,
            server_settings={"application_name": "hoviat-stage-env-identity-check"},
        )
        async with connection.transaction(readonly=True):
            identity = await connection.fetchrow("""
                SELECT current_database() AS database, current_user AS role,
                       host(inet_server_addr()) AS address,
                       inet_server_port() AS port,
                       pg_get_userbyid(datdba) AS owner
                FROM pg_database WHERE datname = current_database()
            """)
            if not identity or tuple(identity.values()) != (DATABASE, ROLE, DB_HOST, DB_PORT, ROLE):
                raise SetupRefused("Staging database identity or ownership does not match the approved target.")
            privileged = await connection.fetchval("""
                SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                FROM pg_roles WHERE rolname = current_user
            """)
            if privileged is not False:
                raise SetupRefused("The staging role must remain nonprivileged.")
            tables = await connection.fetch("""
                SELECT c.relname, pg_get_userbyid(c.relowner) AS owner
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname IN ('services', 'cities')
                  AND c.relkind = 'r'
            """)
            if {row["relname"] for row in tables} != {"services", "cities"} or any(row["owner"] != ROLE for row in tables):
                raise SetupRefused("Required migrated staging tables are missing or have the wrong owner.")
    except SetupRefused:
        raise
    except Exception:
        # Driver exceptions can include connection details. Never print them.
        raise SetupRefused("Read-only database verification failed; inspect staging credentials and schema separately.") from None
    finally:
        if connection is not None:
            try:
                await connection.close()
            except Exception:
                raise SetupRefused("Database connection cleanup failed; no configuration was written.") from None


def public_media_base() -> str:
    value = input("Optional existing public media base URL (blank leaves images unconfigured): ").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        parsed.port
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or "${" in value
            or len(value) > 2048 or any(ord(char) < 33 for char in value)
        ):
            raise ValueError
    except ValueError:
        raise SetupRefused("Media base must be a public HTTPS URL without credentials, query, or fragment.") from None
    return value.rstrip("/")


def environment_text(values: dict[str, str]) -> str:
    # Double-quoted dotenv values preserve exact strings and escape newlines.
    return "# Fresh isolated staging configuration; never copy production credentials.\n" + "".join(
        f"{key}={json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items()
    )


def write_new_files(files: dict[str, Path], contents: dict[str, str]) -> None:
    descriptors = {}
    try:
        # Reserve all names exclusively before writing a credential. The target
        # directories were checked above; O_NOFOLLOW also rejects last-hop races.
        for name, path in files.items():
            descriptors[name] = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.fchmod(descriptors[name], 0o600)
        for name, descriptor in descriptors.items():
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n", closefd=False) as output:
                output.write(contents[name])
                output.flush()
                os.fsync(descriptor)
    except OSError:
        # Do not delete/recreate anything on error. An operator must inspect any
        # partial new files before retrying; existing files are never replaced.
        raise SetupRefused("Environment creation failed. Inspect possible partial files before retrying; none were overwritten.") from None
    finally:
        for descriptor in descriptors.values():
            os.close(descriptor)


async def main() -> None:
    release, files = checked_paths()
    password = getpass.getpass("New staging database password (not printed): ")
    if not password:
        raise SetupRefused("A staging database password is required.")
    await verify_database(password)
    media_base = public_media_base()
    database_url = URL.create(
        "postgresql+asyncpg", username=ROLE, password=password,
        host=DB_HOST, port=DB_PORT, database=DATABASE,
    ).render_as_string(hide_password=False)
    backend = {
        "APP_MODE": "all", "DATABASE_URL": database_url,
        "SECRET_KEY": secrets.token_urlsafe(48), "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "LOGIN_BOT_API_SECRET": secrets.token_urlsafe(48),
        "CRON_SYNC_SECRET": secrets.token_urlsafe(48),
        "DISABLE_BACKGROUND_WORKERS": "true", "DEV_LOGIN_ENABLED": "false",
        "TELEGRAM_API_ENABLED": "false", "MEDIA_WRITES_ENABLED": "false",
        "BOT_API_TOKEN": "disabled-staging", "HILFEN_API_TOKEN": "disabled-staging",
        "SENDER_BOT_TOKEN": "disabled-staging", "EURO_BOT_TOKEN": "disabled-staging",
        "HILFEN_BOT_TOKEN": "disabled-staging", "SNS_LOGIN_BOT_TOKEN": "disabled-staging",
        "TELEGRAM_BASE_URL": "https://disabled.invalid",
        "MAIN_CHANNEL_ID": "0", "MAIN_GROUP_ID": "0", "PUBLIC_CHANNEL_ID": "0",
        "PUBLIC_GROUP_ID": "0", "HILFEN_CHANNEL_ID": "0", "HILFEN_GROUP_ID": "0",
        "FORMATTER_WORKER_URL": "https://disabled.invalid",
        "R2_ENDPOINT_URL": "https://disabled.invalid", "R2_ACCESS_KEY_ID": "disabled",
        "R2_SECRET_ACCESS_KEY": "disabled", "R2_BUCKET_NAME": "disabled-staging",
        "PROFILE_MEDIA_URL": media_base, "SERVICE_MEDIA_URL": media_base,
    }
    consumer = {
        "SNS_API_BASE": f"{API_ORIGIN}/api/sns",
        "SERVICES_API_BASE": f"{API_ORIGIN}/api/services",
        "SNS_USE_MOCK": "0", "SNS_INTERNAL_KEY": "",
        "SNS_TIMEOUT_MS": "10000", "SNS_SEARCH_TTL": "60",
        "NEXT_PUBLIC_BOT_USERNAME": "", "NEXT_PUBLIC_SUPPORT_TELEGRAM_URL": "",
        "NEXT_PUBLIC_SUPPORT_PHONE": "",
    }
    admin = {"VITE_API_URL": "/api"}
    # Recheck immediately before exclusive creation; never infer permission from
    # a previous attempt or reuse a partially configured release.
    verified_release, verified_files = checked_paths()
    if verified_release != release or verified_files != files:
        raise SetupRefused("Release paths changed during preparation.")
    write_new_files(files, {
        "backend": environment_text(backend), "consumer": environment_text(consumer),
        "admin": environment_text(admin),
    })
    print("Created backend, consumer and admin staging environment files with mode 0600.")
    print("Credentials were not printed. No services started; database verification was read-only.")
    print("Telegram, media writes, background workers and development login remain disabled.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SetupRefused as error:
        # Every message in this exception type is static and contains no secret.
        print(f"STOP: {error}", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("STOP: staging environment setup cancelled.", file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Unexpected driver exceptions may include connection details. Do not
        # print their representation, locals or traceback with credentials.
        print("STOP: staging environment setup failed; no service was started. Inspect any partial new files before retrying.", file=sys.stderr)
        sys.exit(1)
