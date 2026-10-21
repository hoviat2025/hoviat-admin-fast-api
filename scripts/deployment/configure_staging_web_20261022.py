"""Configure only the isolated staging HTTPS sites. Run interactively with sudo.

Requires the certificate already issued on the VPS. Production vhosts are not
edited. A password-protected static entry page issues a host-only preview cookie
so the extra preview gate does not compete with application Bearer auth.
"""

import getpass
import grp
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import socket
import subprocess


RELEASE = Path('/home/bardia/apps/sns-staging/releases/20261021-01')
SITE = Path('/etc/nginx/sites-available/hoviat-sns-stage')
ENABLED = Path('/etc/nginx/sites-enabled/hoviat-sns-stage')
CERT = Path('/etc/letsencrypt/live/hoviat-sns-stage-20261022')
ADMIN = Path('/var/www/hoviat-sns-stage-admin-20261022')
GATE = Path('/var/www/hoviat-sns-stage-gate-20261022')
AUTH = Path('/etc/nginx/hoviat-sns-stage-20261022.htpasswd')
SNIPPET = Path('/etc/nginx/snippets/hoviat-sns-stage-20261022.conf')
HOOK = Path('/etc/letsencrypt/renewal-hooks/deploy/hoviat-sns-stage-reload')
BACKUP = Path('/etc/nginx/sites-available/hoviat-sns-stage.before-https-20261022')
WEB_HOST = 'sns-stage.185.202.113.95.nip.io'
ADMIN_HOST = 'sns-admin-stage.185.202.113.95.nip.io'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def write_new(path, content, mode=0o640, gid=0):
    # Refuse overwrites, including dangling symlinks.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(content)
    os.chown(path, 0, gid)
    os.chmod(path, mode)


def main():
    if os.geteuid() != 0 or socket.gethostname() != 'srv5089629844':
        raise SystemExit('Run with sudo on srv5089629844 only.')
    if Path(__file__).resolve().parents[2] != RELEASE / 'backend':
        raise SystemExit('Run the script from the approved staging release only.')
    if not SITE.is_file() or SITE.is_symlink() or ENABLED.resolve() != SITE:
        raise SystemExit('Expected staging-only HTTP site/symlink is missing.')
    old = SITE.read_text()
    if 'listen 443' in old or WEB_HOST not in old or ADMIN_HOST not in old:
        raise SystemExit('Staging config differs from the expected HTTP checkpoint; stop and review.')
    for item in (CERT / 'fullchain.pem', CERT / 'privkey.pem',
                 RELEASE / 'admin/dist/index.html'):
        if not item.is_file():
            raise SystemExit(f'Required file missing: {item}')
    for item in (ADMIN, GATE, AUTH, SNIPPET, HOOK, BACKUP):
        if item.exists() or item.is_symlink():
            raise SystemExit(f'Refusing to overwrite an existing setup file: {item}')
    nginx = shutil.which('nginx') or '/usr/sbin/nginx'
    run(nginx, '-t')
    for port in (18753, 18755):
        with socket.create_connection(('127.0.0.1', port), timeout=5):
            pass
    worker = re.search(r'^\s*user\s+(\S+)(?:\s+(\S+))?\s*;',
                       Path('/etc/nginx/nginx.conf').read_text(), re.MULTILINE)
    if not worker:
        raise SystemExit('Cannot determine Nginx worker user; stop and review.')
    worker_name = worker.group(1)
    gid = grp.getgrnam(worker.group(2)).gr_gid if worker.group(2) else pwd.getpwnam(worker_name).pw_gid
    source = RELEASE / 'admin/dist'
    if source.is_symlink() or any(p.is_symlink() for p in source.rglob('*')):
        raise SystemExit('Admin build contains symlinks; stop and review.')

    password = getpass.getpass('Choose a NEW staging preview password (username: preview): ')
    if len(password) < 12 or '\n' in password or '\r' in password:
        raise SystemExit('Use a password of at least 12 characters, without newlines.')
    if password != getpass.getpass('Repeat staging preview password: '):
        raise SystemExit('Passwords did not match. No setup files created.')
    hashed = run('openssl', 'passwd', '-6', '-stdin', input=password + '\n',
                 text=True, capture_output=True).stdout.strip()
    del password
    if not hashed.startswith('$6$'):
        raise SystemExit('Unexpected password hash format; no setup files created.')
    token = secrets.token_hex(32)

    write_new(BACKUP, old)
    write_new(AUTH, 'preview:' + hashed + '\n', gid=gid)
    shutil.copytree(source, ADMIN)
    for directory, _, files in os.walk(ADMIN):
        os.chmod(directory, 0o755)
        for name in files:
            os.chmod(Path(directory) / name, 0o644)
    GATE.mkdir(mode=0o755)
    os.chmod(GATE, 0o755)  # sudo may preserve a restrictive umask.
    write_new(GATE / 'entry.html',
              '<!doctype html><html><head><meta charset="utf-8">'
              '<meta name="robots" content="noindex,nofollow">'
              '<meta http-equiv="refresh" content="0;url=/">'
              '<title>Staging preview</title></head><body>'
              '<a href="/">Continue to staging</a></body></html>\n', 0o644)
    SNIPPET.parent.mkdir(exist_ok=True)
    write_new(SNIPPET, f'''
ssl_certificate {CERT}/fullchain.pem;
ssl_certificate_key {CERT}/privkey.pem;
include /etc/letsencrypt/options-ssl-nginx.conf;
auth_basic $hoviat_stage_realm;
auth_basic_user_file {AUTH};
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
add_header Cache-Control "private, no-store" always;
client_max_body_size 10m;

# Only this authenticated static response issues the preview cookie.
# Do not put this Set-Cookie header at server level or add `always`.
location = /__preview-entry {{
    auth_basic "Hoviat staging preview";
    alias {GATE}/entry.html;
    default_type text/html;
    add_header Set-Cookie "hoviat_sns_stage_preview={token}; Path=/; Max-Age=28800; Secure; HttpOnly; SameSite=Lax";
    add_header Cache-Control "private, no-store" always;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
}}
''')
    config = f'''# Isolated SNS staging only. Cookie token is a secret; do not paste this file.
map $cookie_hoviat_sns_stage_preview $hoviat_stage_realm {{
    default "Hoviat staging preview";
    "{token}" off;
}}

server {{
    listen 80;
    server_name {WEB_HOST} {ADMIN_HOST};
    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/hoviat-sns-stage-acme;
        default_type text/plain;
        auth_basic off;
    }}
    location / {{ return 301 https://$host$request_uri; }}
}}

server {{
    listen 443 ssl;
    server_name {WEB_HOST};
    include {SNIPPET};
    location / {{
        proxy_pass http://127.0.0.1:18755;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_buffering off;
    }}
}}

server {{
    listen 443 ssl;
    server_name {ADMIN_HOST};
    include {SNIPPET};
    root {ADMIN};
    index index.html;
    location /api/ {{
        # No trailing slash: preserve the backend's /api/... path.
        proxy_pass http://127.0.0.1:18753;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }}
    location / {{ try_files $uri $uri/ /index.html; }}
    location ~ /\\. {{ deny all; }}
}}
'''
    # Replace only the known staging file; restore it if validation/reload fails.
    temp = SITE.with_name(SITE.name + '.https-new')
    try:
        write_new(temp, config)
        temp.replace(SITE)
        run(nginx, '-t')
        run('systemctl', 'reload', 'nginx')
    except BaseException:
        SITE.write_text(old)
        os.chmod(SITE, 0o640)
        run(nginx, '-t')
        run('systemctl', 'reload', 'nginx')
        raise

    HOOK.parent.mkdir(parents=True, exist_ok=True)
    write_new(HOOK, '#!/bin/sh\nset -eu\n' + nginx + ' -t\nsystemctl reload nginx\n', 0o750)
    print('HTTPS staging routes configured. Existing production sites were not edited.')
    print('Username: preview. Password was not printed. Preview cookies last 8 hours.')
    print(f'User panel: https://{WEB_HOST}/__preview-entry')
    print(f'Admin panel: https://{ADMIN_HOST}/__preview-entry')
    print('Database, Telegram, media-write and application-login settings were not changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(
            f'Staging web setup stopped: {error}. '
            'Do not rerun or delete prepared files; share this error for recovery.'
        ) from None
