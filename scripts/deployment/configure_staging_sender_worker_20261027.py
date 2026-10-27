"""Prepare sender callback authentication and only its three staging Nginx routes.

Uses the existing private staging env helpers. Prompts for the sender Worker's
API_SECRET; never prints it. Restarts only the staging API before exposing the
callbacks. Production services, Telegram webhooks and queue settings are not edited.
"""
import getpass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import sys

from enable_staging_features_20261027 import (
    BACKEND, BACKEND_ENV, BACKUPS, SITE, ENABLED, atomic_env, read_env,
    replace_settings, make_url,
)

ANCHOR = '''    server_name sns-admin-stage.185.202.113.95.nip.io;
    include /etc/nginx/snippets/hoviat-sns-stage-20261022.conf;'''
PATHS = (
    '/webhook/hoviat/v1/eurobot/set_group_message_id_test',
    '/webhook/hoviat/v1/eurobot/set_public_message_id_test',
    '/webhook/hoviat/v1/hilfen/set_hilfen_message_id',
)


def main():
    if (sys.argv[1:] or os.geteuid() != 0 or socket.gethostname() != 'srv5089629844'
            or Path(__file__).resolve().parents[2] != BACKEND or Path.cwd() != BACKEND):
        raise SystemExit('Run with sudo from the approved staging backend only.')
    if SITE.is_symlink() or SITE.resolve() != SITE or ENABLED.resolve() != SITE:
        raise SystemExit('Unexpected staging Nginx paths; stop and review.')
    old_site = SITE.read_text()
    if old_site.count(ANCHOR) != 1 or any(path in old_site for path in PATHS):
        raise SystemExit('Callback routes already exist or the site differs; stop and review.')
    old_env, values = read_env(BACKEND_ENV)
    database = make_url(values.get('DATABASE_URL') or '')
    if (database.host != '127.0.0.1' or database.username != 'hoviat_sns_stage'
            or database.database != 'hoviat_sns_stage_20261021'):
        raise SystemExit('Not the approved isolated staging database; stopped.')
    subprocess.run(['/usr/sbin/nginx', '-t'], check=True)
    secret = getpass.getpass('Enter the SAME API_SECRET used at the top of the test sender Worker: ')
    if not secret or any(char in secret for char in ('\r', '\n', '\x00')):
        raise SystemExit('A nonempty single-line API_SECRET is required.')
    if secret != getpass.getpass('Repeat API_SECRET: '):
        raise SystemExit('Passwords did not match. Nothing changed.')
    if BACKUPS.is_symlink() or (BACKUPS.exists() and BACKUPS.stat().st_uid != 0):
        raise SystemExit('Unexpected private backup directory; stopped.')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    backup = Path(tempfile.mkdtemp(prefix='sender-worker-', dir=BACKUPS))
    for name, content in (('backend.env', old_env), ('nginx.conf', old_site)):
        target = backup / name
        target.write_text(content)
        os.chmod(target, 0o600)

    routes = '\n    # Historical _test suffixes are also used by production.\n'
    routes += '    # These routes reach ONLY the isolated staging API and require its sender secret.\n'
    for path in PATHS:
        routes += f'''    location = {path} {{
        auth_basic off;
        limit_except PUT {{ deny all; }}
        client_max_body_size 256k;
        proxy_pass http://127.0.0.1:18753;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }}
'''
    new_env = replace_settings(old_env, {'SENDER_WEBHOOK_API_SECRET': secret})
    del secret
    print('Private backups: ' + str(backup))
    atomic_env(BACKEND_ENV, new_env, old_env)
    # Load backend authentication before opening its callback routes externally.
    subprocess.run(['systemctl', 'restart', 'hoviat-sns-stage-api.service'], check=True)
    temporary = SITE.with_name(SITE.name + '.sender-new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(old_site.replace(ANCHOR, ANCHOR + '\n' + routes, 1))
    try:
        temporary.replace(SITE)
        subprocess.run(['/usr/sbin/nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    except BaseException:
        # Backend keeps its new authentication; only routing is rolled back.
        shutil.copyfile(backup / 'nginx.conf', SITE)
        os.chmod(SITE, 0o600)
        subprocess.run(['/usr/sbin/nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        raise
    print('Sender authentication and three staging callback routes configured.')
    print('Only the staging API was restarted. Production and queue settings were not changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ValueError):
        raise SystemExit('Sender setup stopped. Keep the private backups and send the error above; do not rerun blindly.') from None
