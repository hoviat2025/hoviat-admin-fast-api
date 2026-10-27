"""Prepare approved staging media/dev-login settings; never restart services.

Run with sudo using this release's backend/.venv/bin/python. Production is read
only, and only the six explicitly listed media settings are copied. No network
requests, builds, database connections or systemd reloads are performed.
"""

import io
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from dotenv import dotenv_values
from dotenv.parser import parse_stream
from sqlalchemy.engine import make_url


RELEASE = Path('/home/bardia/apps/sns-staging/releases/20261021-01')
BACKEND = RELEASE / 'backend'
PRODUCTION = Path('/home/bardia/apps/api/backend/.env')
BACKEND_ENV = BACKEND / '.env'
CONSUMER_ENV = RELEASE / 'consumer/.env.local'
BACKUPS = Path('/home/bardia/apps/sns-staging/private-backups')
DROPIN = Path('/etc/systemd/system/hoviat-sns-stage-api.service.d/20-staging-features.conf')
SITE = Path('/etc/nginx/sites-available/hoviat-sns-stage')
ENABLED = Path('/etc/nginx/sites-enabled/hoviat-sns-stage')
SNIPPET = Path('/etc/nginx/snippets/hoviat-sns-stage-20261022.conf')
SERVICE = 'hoviat-sns-stage-api.service'
ORIGIN = 'https://sns-stage.185.202.113.95.nip.io'
MEDIA_KEYS = ('R2_ENDPOINT_URL', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY',
              'R2_BUCKET_NAME', 'PROFILE_MEDIA_URL', 'SERVICE_MEDIA_URL')
FLAGS = {'MEDIA_WRITES_ENABLED': 'true', 'DEV_LOGIN_ENABLED': 'true',
         'DISABLE_BACKGROUND_WORKERS': 'true', 'TELEGRAM_API_ENABLED': 'false'}


class Refused(Exception):
    """Only static messages or explicitly approved key names belong here."""


def regular(path):
    if path.resolve(strict=True) != path or not stat.S_ISREG(path.lstat().st_mode):
        raise Refused('A required configuration file is missing, linked or not regular.')


def read_env(path):
    regular(path)
    content = path.read_text(encoding='utf-8')
    if any(binding.error for binding in parse_stream(io.StringIO(content))):
        raise Refused('An environment file has invalid dotenv syntax.')
    return content, dict(dotenv_values(stream=io.StringIO(content), interpolate=True))


def https_url(value):
    try:
        parsed = urlsplit(value)
        parsed.port
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not parsed.query and not parsed.fragment
                and '${' not in value and len(value) <= 2048
                and all(ord(char) > 32 for char in value))
    except ValueError:
        return False


def replace_settings(content, settings):
    # Preserve every unrelated binding/comment, including multiline values.
    remaining = dict(settings)
    output = []
    for binding in parse_stream(io.StringIO(content)):
        if binding.key in settings:
            if binding.key in remaining:
                value = remaining.pop(binding.key).replace('\\', '\\\\').replace("'", "\\'")
                output.append(f"{binding.key}='{value}'\n")
            # Discard duplicate definitions of a setting we explicitly change.
        else:
            output.append(binding.original.string)
    result = ''.join(output)
    if result and not result.endswith('\n'):
        result += '\n'
    for key, value in remaining.items():
        value = value.replace('\\', '\\\\').replace("'", "\\'")
        result += f"{key}='{value}'\n"
    return result


def check_service_and_gate():
    result = subprocess.run(
        ['systemctl', 'show', SERVICE, '--property=WorkingDirectory', '--property=ExecStart'],
        capture_output=True, text=True, check=True, timeout=15,
    )
    properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    command = properties.get('ExecStart', '')
    hosts = re.findall(r'--host(?:=|\s+)([^\s;]+)', command)
    ports = re.findall(r'--port(?:=|\s+)([^\s;]+)', command)
    if properties.get('WorkingDirectory') != str(BACKEND) or hosts != ['127.0.0.1'] or ports != ['18753']:
        raise Refused('Staging API service working directory or loopback binding differs from the approved target.')
    regular(SITE)
    regular(SNIPPET)
    if not ENABLED.is_symlink() or ENABLED.resolve(strict=True) != SITE:
        raise Refused('The protected staging Nginx site is not enabled as expected.')
    site = SITE.read_text(encoding='utf-8')
    snippet = SNIPPET.read_text(encoding='utf-8')
    if (not re.search(r'^\s*include\s+' + re.escape(str(SNIPPET)) + r'\s*;', site, re.M)
            or 'sns-stage.185.202.113.95.nip.io' not in site
            or not re.search(r'^\s*auth_basic\s+(?!off\s*;)[^;]+;', snippet, re.M)
            or not re.search(r'^\s*auth_basic_user_file\s+[^;]+;', snippet, re.M)):
        raise Refused('The existing staging Nginx preview protection could not be verified.')


def atomic_env(path, content, original):
    regular(path)
    if path.read_text(encoding='utf-8') != original:
        raise Refused('An environment file changed during preparation; inspect backups before retrying.')
    owner = path.stat()
    fd, temporary = tempfile.mkstemp(prefix='.staging-features-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), owner.st_uid, owner.st_gid)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    if sys.argv[1:]:
        raise Refused('This script takes no arguments.')
    if sys.platform != 'linux' or os.geteuid() != 0 or socket.gethostname() != 'srv5089629844':
        raise Refused('Run with sudo on the approved staging VPS only.')
    script = Path(__file__).absolute()
    if (script.resolve(strict=True) != script or script.parents[2] != BACKEND
            or Path(sys.prefix).absolute() != BACKEND / '.venv'
            or Path.cwd() != BACKEND):
        raise Refused('Run from the exact approved staging backend with its .venv/bin/python.')
    if DROPIN.exists() or DROPIN.is_symlink():
        raise Refused('The staging feature drop-in already exists; refusing to overwrite it.')
    if DROPIN.parent.exists() or DROPIN.parent.is_symlink():
        if (DROPIN.parent.resolve(strict=True) != DROPIN.parent
                or not DROPIN.parent.is_dir() or DROPIN.parent.stat().st_uid != 0):
            raise Refused('The systemd drop-in directory must be root-owned without links.')
    elif DROPIN.parent.parent.resolve(strict=True) != DROPIN.parent.parent:
        raise Refused('The systemd configuration parent must not contain links.')
    check_service_and_gate()
    backend_original, backend = read_env(BACKEND_ENV)
    consumer_original, consumer = read_env(CONSUMER_ENV)
    database = make_url(backend.get('DATABASE_URL') or '')
    if (database.drivername not in ('postgresql', 'postgresql+asyncpg')
            or database.username != 'hoviat_sns_stage' or database.host != '127.0.0.1'
            or database.database != 'hoviat_sns_stage_20261021'
            or database.port not in (None, 5432) or database.query):
        raise Refused('Staging database settings differ from the approved isolated database.')
    if (consumer.get('SNS_API_BASE') != 'http://127.0.0.1:18753/api/sns'
            or consumer.get('SERVICES_API_BASE') != 'http://127.0.0.1:18753/api/services'):
        raise Refused('Consumer API settings must retain the approved loopback staging API.')
    _, production = read_env(PRODUCTION)
    media = {key: production.get(key) or '' for key in MEDIA_KEYS}
    media['SERVICE_MEDIA_URL'] = media['SERVICE_MEDIA_URL'] or media['PROFILE_MEDIA_URL']
    missing = [key for key, value in media.items() if not value.strip()]
    if missing:
        raise Refused('Missing required production keys: ' + ', '.join(missing))
    invalid = [key for key, value in media.items()
               if '\n' in value or '\r' in value or '\x00' in value or '${' in value]
    invalid += [key for key in ('R2_ENDPOINT_URL', 'PROFILE_MEDIA_URL', 'SERVICE_MEDIA_URL')
                if not https_url(media[key]) and key not in invalid]
    if invalid:
        raise Refused('Invalid production settings: ' + ', '.join(invalid))
    backend_new = replace_settings(backend_original, {**media, **FLAGS})
    consumer_new = replace_settings(consumer_original, {'SNS_DEV_LOGIN_ORIGIN': ORIGIN})
    # Check serialization before writing; unrelated effective settings must survive.
    for original, updated, changes in ((backend, backend_new, {**media, **FLAGS}),
                                       (consumer, consumer_new, {'SNS_DEV_LOGIN_ORIGIN': ORIGIN})):
        parsed = dict(dotenv_values(stream=io.StringIO(updated), interpolate=True))
        if parsed != {**original, **changes}:
            raise Refused('Environment serialization would change unrelated settings; stopped before writing.')
    if BACKUPS.exists():
        if (BACKUPS.resolve(strict=True) != BACKUPS or not BACKUPS.is_dir()
                or BACKUPS.stat().st_uid != 0 or stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700):
            raise Refused('The private backup directory must be root-owned with mode 0700 and no links.')
    else:
        if BACKUPS.parent.resolve(strict=True) != BACKUPS.parent:
            raise Refused('The staging backup parent must not contain links.')
        BACKUPS.mkdir(mode=0o700)
        os.chmod(BACKUPS, 0o700)
    backup = Path(tempfile.mkdtemp(prefix='features-20261027-', dir=BACKUPS))
    os.chmod(backup, 0o700)
    for name, path in (('backend.env', BACKEND_ENV), ('consumer.env.local', CONSUMER_ENV)):
        regular(path)
        with (backup / name).open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(path.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
    # All validation precedes mutations. Backups remain for manual recovery if a
    # later write fails; no unsafe automatic rollback or service restart occurs.
    try:
        atomic_env(BACKEND_ENV, backend_new, backend_original)
        atomic_env(CONSUMER_ENV, consumer_new, consumer_original)
        DROPIN.parent.mkdir(mode=0o755, exist_ok=True)
        if DROPIN.parent.resolve(strict=True) != DROPIN.parent or not DROPIN.parent.is_dir():
            raise Refused('The systemd drop-in directory must not contain links.')
        fd = os.open(DROPIN, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write('[Service]\n' + ''.join(f'Environment="{key}={value}"\n' for key, value in FLAGS.items()))
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise Refused('Configuration update stopped; partial changes may exist. Private backups: ' + str(backup)) from None
    print('Updated staging backend/.env, consumer/.env.local and 20-staging-features.conf.')
    print('Private backups: ' + str(backup))
    print('Services were not restarted. Systemd was not reloaded. No builds were run.')


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print('STOP: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except BaseException:
        # Exception representations and tracebacks may contain credentials.
        print('STOP: staging configuration preparation failed; no services were restarted. Inspect private backups and possible partial files before retrying.', file=sys.stderr)
        sys.exit(1)
