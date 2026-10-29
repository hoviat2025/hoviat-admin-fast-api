"""Prepare NEW production release env files; never start apps or change live envs."""
import ast
import io
import os
from pathlib import Path
import secrets
import socket
import stat
import subprocess
import sys
from urllib.parse import urlsplit

from dotenv import dotenv_values
from dotenv.parser import parse_stream
from sqlalchemy.engine import make_url

HOST = 'srv5089629844'
RELEASE = Path('/home/bardia/apps/sns-production/releases/20261029-01')
LIVE = Path('/home/bardia/apps/api/backend')
LIVE_REVISION = 'c8b2372b5ccbc575b7cd2037deb1c0c60b00c8e0'
PRIVATE = Path('/home/bardia/apps/sns-production/private')
IDS = dict(MAIN_CHANNEL_ID='-1001129100618', MAIN_GROUP_ID='-1002086581533',
           PUBLIC_CHANNEL_ID='-1003443613002', PUBLIC_GROUP_ID='-1003238310244',
           HILFEN_CHANNEL_ID='-1002026011030', HILFEN_GROUP_ID='-1002156702345')
FLAGS = dict(APP_MODE='all', DEV_LOGIN_ENABLED='false',
             DISABLE_BACKGROUND_WORKERS='false', TELEGRAM_API_ENABLED='true',
             MEDIA_WRITES_ENABLED='true')


class Refused(Exception):
    """Messages must contain static descriptions/key names, never values."""


def parse_env(content):
    bindings = list(parse_stream(io.StringIO(content)))
    if any(binding.error for binding in bindings):
        raise Refused('Invalid dotenv syntax; no configuration prepared.')
    return dict(dotenv_values(stream=io.StringIO(content), interpolate=False))


def updated_text(content, updates):
    # Preserve unrelated bindings/comments verbatim. Escape both supported
    # single-quoted dotenv escapes, including literal backslashes in passwords.
    remaining = dict(updates)
    lines = []
    def line(key, value):
        value = value.replace('\\', '\\\\').replace("'", "\\'")
        return f"{key}='{value}'\n"
    for binding in parse_stream(io.StringIO(content)):
        if binding.key not in updates:
            lines.append(binding.original.string)
        elif binding.key in remaining:
            lines.append(line(binding.key, remaining.pop(binding.key)))
    result = ''.join(lines)
    if result and not result.endswith('\n'):
        result += '\n'
    return result + ''.join(line(key, value) for key, value in remaining.items())


def required_settings(source):
    """Read declarations without importing Settings or initializing the app."""
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Settings')
    return {node.target.id for node in cls.body if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name) and node.value is None}


def public_url(value):
    try:
        parsed = urlsplit(value)
        parsed.port
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not parsed.query and not parsed.fragment
                and not any(ord(char) <= 32 for char in value))
    except (ValueError, TypeError):
        return False


def build_plan(backend_text, consumer_text, admin_text, process_env, required, token_factory=secrets.token_urlsafe):
    """Pure planning: only supplied text/mappings; no app, DB, network or writes."""
    backend = parse_env(backend_text)
    parse_env(consumer_text)
    parse_env(admin_text)
    for key in required:
        value = backend.get(key)
        if not isinstance(value, str) or not value.strip() or '${' in value or '\x00' in value:
            raise Refused('A required production setting is missing or uses interpolation: ' + key)
    # The inspected live unit exports .env with EnvironmentFile. Require these
    # settings in /proc as well, so pending edits cannot silently change identity.
    critical = set(required) | {'PROFILE_MEDIA_URL'}
    critical |= {key for key in ('ALGORITHM', 'ACCESS_TOKEN_EXPIRE_MINUTES', 'SERVICE_MEDIA_URL')
                 if backend.get(key) or key in process_env}
    for key in critical:
        if key not in process_env or process_env[key] != backend.get(key):
            raise Refused('Live process and production env disagree or omit: ' + key)
    if backend.get('SENDER_WEBHOOK_API_SECRET') and process_env.get('SENDER_WEBHOOK_API_SECRET') != backend['SENDER_WEBHOOK_API_SECRET']:
        raise Refused('Live sender API setting and production env disagree.')
    try:
        database = make_url(backend['DATABASE_URL'])
        valid_db = (database.drivername in ('postgresql', 'postgresql+asyncpg')
                    and database.database == 'hoviat' and database.username == 'hoviat'
                    and database.host in ('127.0.0.1', 'localhost') and database.port in (None, 5432))
    except Exception:
        valid_db = False
    if not valid_db or any(backend.get(key) != value for key, value in IDS.items()):
        raise Refused('Production database identity or real channel/group IDs differ.')
    media = backend.get('SERVICE_MEDIA_URL') or backend.get('PROFILE_MEDIA_URL')
    if not public_url(media) or not public_url(backend.get('R2_ENDPOINT_URL')):
        raise Refused('Production media/storage public URL configuration needs review.')
    sender_api = backend.get('SENDER_WEBHOOK_API_SECRET') or token_factory(32)
    if not sender_api or any(char in sender_api for char in '\r\n\x00') or sender_api.strip() != sender_api:
        raise Refused('Sender API secret must be a nonempty single-line value.')
    updated_backend = updated_text(backend_text, {**FLAGS, 'SENDER_WEBHOOK_API_SECRET': sender_api, 'SERVICE_MEDIA_URL': media})
    consumer = updated_text(consumer_text, {
        'SNS_API_BASE': 'http://127.0.0.1:8000/api/sns',
        'SERVICES_API_BASE': 'http://127.0.0.1:8000/api/services',
        'SNS_USE_MOCK': '0', 'SNS_DEV_LOGIN_ORIGIN': '',
        'NEXT_PUBLIC_BOT_USERNAME': 'hoviatloginbot',
    })
    admin = updated_text(admin_text, {'VITE_API_URL': 'https://185.202.113.95.nip.io/api'})
    worker = updated_text('# PRIVATE: copy values into Cloudflare; do not source this file in a shell.\n', {
        'SENDER_API_SECRET': sender_api, 'SENDER_WEBHOOK_SECRET': token_factory(32),
        'SENDER_BOT_TOKEN': backend['SENDER_BOT_TOKEN'],
        'LOGIN_BOT_TOKEN': backend['SNS_LOGIN_BOT_TOKEN'],
        'LOGIN_API_SECRET': backend['LOGIN_BOT_API_SECRET'],
        'LOGIN_WEBHOOK_SECRET': token_factory(32),
    })
    planned = parse_env(updated_backend)
    for key, value in backend.items():
        if key not in FLAGS and key not in ('SENDER_WEBHOOK_API_SECRET', 'SERVICE_MEDIA_URL') and planned.get(key) != value:
            raise Refused('A preserved production setting failed round-trip validation: ' + key)
    if any(planned.get(key) != value for key, value in FLAGS.items()):
        raise Refused('Prepared production flags failed validation.')
    if planned.get('SENDER_WEBHOOK_API_SECRET') != sender_api or planned.get('SERVICE_MEDIA_URL') != media:
        raise Refused('Prepared sender/media settings failed round-trip validation.')
    for text in (consumer, admin, worker):
        parse_env(text)
    return {'backend': updated_backend, 'consumer': consumer, 'admin': admin, 'worker': worker}


def regular(path):
    if path.resolve(strict=True) != path.absolute() or not stat.S_ISREG(path.lstat().st_mode):
        raise Refused('A required file is missing, linked or not regular.')


def write_plan(plan, release, private, owner=None):
    """Exclusive NEW-file writes; refuse the complete operation on any existing target."""
    directories = [release / name for name in ('backend', 'consumer', 'admin')]
    for directory in directories:
        if directory.resolve(strict=True) != directory.absolute() or not directory.is_dir():
            raise Refused('Candidate directories must exist without linked path components.')
    if private.parent.resolve(strict=True) != private.parent.absolute():
        raise Refused('Private settings parent is linked or missing.')
    if private.exists() and (private.is_symlink() or private.resolve(strict=True) != private.absolute() or not private.is_dir()):
        raise Refused('Private settings directory is unsafe.')
    targets = dict(backend=release / 'backend/.env', consumer=release / 'consumer/.env.local',
                   admin=release / 'admin/.env.production', worker=private / 'worker-settings-20261029.env')
    # Refuse other dotenv overlays too: a stale local file could override a build.
    for directory in directories:
        if any(not path.name.endswith(('.example', '.sample')) for path in directory.glob('.env*')):
            raise Refused('Candidate environment files already exist; nothing was overwritten.')
    if any(path.exists() or path.is_symlink() for path in targets.values()):
        raise Refused('A prepared file already exists; retain it and do not rerun.')
    private.mkdir(mode=0o700, exist_ok=True)
    for directory in [*directories, private]:
        os.chmod(directory, 0o700)
        if owner is not None:
            os.chown(directory, *owner)
    # Keep generated passwords recoverable first if a later exclusive write fails.
    for name in ('worker', 'backend', 'consumer', 'admin'):
        descriptor = os.open(targets[name], os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(plan[name])
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(targets[name], 0o600)
        if owner is not None:
            os.chown(targets[name], *owner)


def main():
    if (sys.argv[1:] or sys.platform != 'linux' or os.geteuid() != 0
            or socket.gethostname() != HOST or Path(__file__).absolute().resolve() != Path(__file__).absolute()
            or Path(__file__).absolute().parents[2] != RELEASE / 'backend'
            or Path(sys.prefix).resolve() != RELEASE / 'backend/.venv'
            or Path.cwd() != RELEASE / 'backend'):
        raise Refused('Use sudo with the candidate backend venv from its approved VPS directory.')
    import pwd
    account = pwd.getpwnam('bardia')
    for directory in (LIVE, RELEASE / 'backend', RELEASE / 'consumer', RELEASE / 'admin'):
        if directory.resolve(strict=True) != directory or directory.stat().st_uid != account.pw_uid:
            raise Refused('A live/candidate directory path or owner differs from the approved target.')
    properties = subprocess.run(['systemctl', 'show', 'hoviat-api.service', '-p', 'ActiveState', '-p', 'WorkingDirectory', '-p', 'MainPID'], capture_output=True, text=True, check=True, timeout=15)
    service = dict(line.split('=', 1) for line in properties.stdout.splitlines() if '=' in line)
    if service.get('ActiveState') != 'active' or service.get('WorkingDirectory') != str(LIVE) or not service.get('MainPID', '').isdigit() or int(service['MainPID']) <= 1:
        raise Refused('The existing production API is not active at the expected location.')
    revision = subprocess.run(['git', '-C', str(LIVE), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    if revision != LIVE_REVISION:
        raise Refused('The live API revision changed; inspect it before preparation.')
    process_bytes = Path('/proc') / service['MainPID'] / 'environ'
    process = dict(item.split('=', 1) for item in process_bytes.read_bytes().decode('utf-8').split('\x00') if '=' in item)
    sources = [LIVE / '.env', Path('/home/bardia/apps/discover/.env.local'), Path('/home/bardia/apps/admin-panel/.env')]
    for path in sources:
        regular(path)
    required = required_settings((RELEASE / 'backend/app/core/config.py').read_text(encoding='utf-8'))
    originals = [path.read_text(encoding='utf-8') for path in sources]
    plan = build_plan(*originals, process, required)
    if any(path.read_text(encoding='utf-8') != content for path, content in zip(sources, originals)):
        raise Refused('A live environment file changed during preparation; nothing was written.')
    current_pid = subprocess.run(['systemctl', 'show', 'hoviat-api.service', '-p', 'MainPID', '--value'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    if current_pid != service['MainPID']:
        raise Refused('The live API process changed during preparation; nothing was written.')
    write_plan(plan, RELEASE, PRIVATE, (account.pw_uid, account.pw_gid))
    print('Prepared NEW backend/.env, consumer/.env.local and admin/.env.production (0600).')
    print('Private Worker settings: ' + str(PRIVATE / 'worker-settings-20261029.env'))
    print('No secret values printed. Live envs, services, database, Telegram and Cloudflare were not changed.')


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        raise SystemExit('Production preparation stopped: ' + str(error)) from None
    except Exception:
        raise SystemExit('Production preparation stopped; retain any prepared files for review. No service was restarted.') from None
