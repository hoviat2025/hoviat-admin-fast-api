"""Render private Cloudflare copies; no requests, webhook changes or app imports."""
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sys

from dotenv import dotenv_values

RELEASE = Path('/home/bardia/apps/sns-production/releases/20261029-01')
PRIVATE = Path('/home/bardia/apps/sns-production/private')
LIVE = Path('/home/bardia/apps/api/backend')


class Refused(Exception):
    pass


def replace_one(source, pattern, prefix, value):
    result, count = re.subn(pattern, lambda _: prefix + json.dumps(value) + ',', source)
    if count != 1:
        raise Refused('The login Worker template differs from the reviewed version.')
    return result


def render_workers(sender, login, settings):
    for key, value in (('WEBHOOK_SECRET', settings['sender_webhook_secret']),
                       ('API_SECRET', settings['sender_api_secret'])):
        placeholder = f'const {key} = "";'
        if sender.count(placeholder) != 1:
            raise Refused('The sender Worker template differs from the reviewed version.')
        sender = sender.replace(placeholder, f'const {key} = {json.dumps(value)};')
    for key, value in (('BOT_TOKEN', settings['login_bot_token']),
                       ('API_SECRET', settings['login_api_secret']),
                       ('WEBHOOK_SECRET', settings['login_webhook_secret'])):
        login = replace_one(login, rf'(?m)^  {key}: "",', f'  {key}: ', value)
    return sender, login


def worker_settings(candidate, live, existing=None):
    # These values were copied from production; fail rather than silently
    # changing a bot identity or login credential during release preparation.
    for key in ('DATABASE_URL', 'SECRET_KEY', 'SENDER_BOT_TOKEN',
                'SNS_LOGIN_BOT_TOKEN', 'LOGIN_BOT_API_SECRET'):
        if not candidate.get(key) or candidate.get(key) != live.get(key):
            raise Refused('Candidate and live configuration differ: ' + key)
    sender_api = candidate.get('SENDER_WEBHOOK_API_SECRET', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,}', sender_api):
        raise Refused('The candidate sender API secret is missing or invalid.')
    stable = {
        'sender_api_secret': sender_api,
        'sender_bot_token': live['SENDER_BOT_TOKEN'],
        'login_bot_token': live['SNS_LOGIN_BOT_TOKEN'],
        'login_api_secret': live['LOGIN_BOT_API_SECRET'],
    }
    if existing is not None:
        if any(existing.get(key) != value for key, value in stable.items()):
            raise Refused('Saved Worker credentials differ; existing files were retained.')
        for key in ('sender_webhook_secret', 'login_webhook_secret'):
            if not re.fullmatch(r'[A-Za-z0-9_-]{40,}', existing.get(key, '')):
                raise Refused('Saved webhook credentials need review.')
        if len({existing['sender_webhook_secret'], existing['login_webhook_secret'], sender_api}) != 3:
            raise Refused('Webhook credentials must be distinct.')
        return existing
    return {**stable, 'sender_webhook_secret': secrets.token_urlsafe(32),
            'login_webhook_secret': secrets.token_urlsafe(32)}


def save_private(path, content, owner=None):
    if path.is_symlink():
        raise Refused('A private file is linked; nothing was overwritten.')
    if path.exists():
        if path.read_text(encoding='utf-8') != content:
            raise Refused('A private file was edited; nothing was overwritten.')
    else:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    path.chmod(0o600)
    if owner is not None:
        os.chown(path, *owner)


def saved_settings(metadata, legacy):
    for path in (metadata, legacy):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise Refused('A saved settings path is linked or not a regular file.')
    existing = json.loads(metadata.read_text()) if metadata.exists() else None
    if legacy.exists():
        values = dict(dotenv_values(legacy, interpolate=False))
        mapped = {key: values.get(key.upper()) for key in (
            'sender_api_secret', 'sender_bot_token', 'sender_webhook_secret',
            'login_bot_token', 'login_api_secret', 'login_webhook_secret')}
        if existing is not None and existing != mapped:
            raise Refused('The saved Worker settings sources disagree; nothing was overwritten.')
        existing = mapped
    return existing


def main():
    if (sys.platform != 'linux' or os.geteuid() != 0 or socket.gethostname() != 'srv5089629844'
            or Path(__file__).resolve().parents[2] != RELEASE / 'backend'
            or Path.cwd() != RELEASE / 'backend'):
        raise Refused('Run using sudo from the approved production candidate backend.')
    import pwd
    account = pwd.getpwnam('bardia')
    for directory in (RELEASE / 'backend', LIVE, PRIVATE.parent):
        if directory.resolve(strict=True) != directory:
            raise Refused('An approved directory is linked or missing.')
    candidate_path, live_path = RELEASE / 'backend/.env', LIVE / '.env'
    for path in (candidate_path, live_path):
        if path.resolve(strict=True) != path or not path.is_file():
            raise Refused('An expected environment file is linked or missing.')
    if PRIVATE.is_symlink() or (PRIVATE.exists() and not PRIVATE.is_dir()):
        raise Refused('The private settings directory needs review.')
    metadata = PRIVATE / 'production-worker-settings-20261029.json'
    existing = saved_settings(metadata, PRIVATE / 'worker-settings-20261029.env')
    settings = worker_settings(dict(dotenv_values(candidate_path, interpolate=False)),
                               dict(dotenv_values(live_path, interpolate=False)), existing)
    templates = RELEASE / 'backend/scripts/cloudflare-workers'
    sender, login = render_workers((templates / 'sender-bot-webhook.js').read_text(encoding='utf-8'),
                                  (templates / 'sns-login-bot-production.js').read_text(encoding='utf-8'), settings)
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    PRIVATE.chmod(0o700)
    os.chown(PRIVATE, account.pw_uid, account.pw_gid)
    owner = account.pw_uid, account.pw_gid
    save_private(metadata, json.dumps(settings, indent=2) + '\n', owner)
    save_private(PRIVATE / 'sender-bot-production.js', sender, owner)
    save_private(PRIVATE / 'sns-login-bot-production.js', login, owner)
    print('Prepared private sender-bot-production.js and sns-login-bot-production.js.')
    print('Folder: ' + str(PRIVATE))
    print('Secrets were not printed. Nothing was deployed, sent, registered or restarted.')


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        raise SystemExit('Worker preparation stopped: ' + str(error)) from None
    except Exception:
        raise SystemExit('Worker preparation stopped; existing files were retained for review. No external calls were made.') from None
