"""Expose Eurobot/Hilfen staging API prefixes; keep backend Bearer authentication."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from enable_staging_features_20261027 import (
    BACKEND, BACKEND_ENV, BACKUPS, SITE, ENABLED, read_env, make_url, atomic_env,
)

ANCHOR = '''    server_name sns-admin-stage.185.202.113.95.nip.io;
    include /etc/nginx/snippets/hoviat-sns-stage-20261022.conf;'''
PREFIXES = ('/webhook/hoviat/v1/eurobot/', '/webhook/hoviat/v1/hilfen/')


def run(*args):
    subprocess.run(args, check=True)


def main():
    os.umask(0o077)
    if (sys.argv[1:] or os.geteuid() != 0 or socket.gethostname() != 'srv5089629844'
            or Path(__file__).resolve().parents[2] != BACKEND or Path.cwd() != BACKEND):
        raise SystemExit('Run with sudo from the approved staging backend only.')
    if SITE.is_symlink() or SITE.resolve() != SITE or ENABLED.resolve() != SITE:
        raise SystemExit('Unexpected staging Nginx paths; stopped.')
    old = SITE.read_text()
    if old.count(ANCHOR) != 1 or SITE.stat().st_uid != 0:
        raise SystemExit('Unexpected staging admin server configuration; stopped.')
    _, values = read_env(BACKEND_ENV)
    database = make_url(values.get('DATABASE_URL') or '')
    if (database.host != '127.0.0.1' or database.port not in (None, 5432)
            or database.username != 'hoviat_sns_stage'
            or database.database != 'hoviat_sns_stage_20261021'
            or values.get('APP_MODE') != 'all'):
        raise SystemExit('Expected the isolated staging database and APP_MODE=all; stopped.')
    for key in ('BOT_API_TOKEN', 'HILFEN_API_TOKEN', 'SENDER_WEBHOOK_API_SECRET'):
        value = (values.get(key) or '').strip()
        if not value or value.lower() in ('disabled', 'disabled-staging', 'changeme', 'replace_me'):
            raise SystemExit('Set a real staging API password for ' + key + ' in backend/.env first.')
    directory = subprocess.run(
        ['systemctl', 'show', 'hoviat-sns-stage-api.service', '-p', 'WorkingDirectory', '--value'],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    if directory != str(BACKEND):
        raise SystemExit('Staging API service points at an unexpected directory; stopped.')
    routes = '\n    # Eurobot/Hilfen member APIs require their backend Bearer API passwords.\n'
    routes += '    # Exact sender callback locations still take precedence and require their own secret.\n'
    missing = []
    for prefix in PREFIXES:
        if 'location ^~ ' + prefix + ' {' in old:
            continue
        if 'location ' + prefix in old:
            raise SystemExit('An unexpected existing bot API prefix needs review; stopped.')
        missing.append(prefix)
        routes += f'''    location ^~ {prefix} {{
        auth_basic off;
        proxy_pass http://127.0.0.1:18753;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }}
'''
    run('/usr/sbin/nginx', '-t')
    if not missing:
        print('Both staging API prefixes are already exposed. No changes made.')
        return
    if BACKUPS.is_symlink() or BACKUPS.resolve() != BACKUPS or BACKUPS.stat().st_uid != 0:
        raise SystemExit('Unexpected private backup directory; stopped.')
    backup = Path(tempfile.mkdtemp(prefix='bot-api-routing-', dir=BACKUPS))
    saved = backup / 'nginx.conf'
    saved.write_text(old)
    os.chmod(saved, 0o600)
    print('Private routing backup: ' + str(backup), flush=True)
    # Load any API-password edits before allowing external member requests.
    run('systemctl', 'restart', 'hoviat-sns-stage-api.service')
    new = old.replace(ANCHOR, ANCHOR + '\n' + routes, 1)
    try:
        atomic_env(SITE, new, old)
        run('/usr/sbin/nginx', '-t')
        run('systemctl', 'reload', 'nginx')
    except BaseException:
        atomic_env(SITE, old, SITE.read_text())
        run('/usr/sbin/nginx', '-t')
        run('systemctl', 'reload', 'nginx')
        raise
    print('Eurobot: https://sns-admin-stage.185.202.113.95.nip.io' + PREFIXES[0])
    print('Hilfen:  https://sns-admin-stage.185.202.113.95.nip.io' + PREFIXES[1])
    print('Backend API-password checks remain enabled. Production was not changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError):
        raise SystemExit('API routing setup stopped; keep the backup and share the error above.') from None
