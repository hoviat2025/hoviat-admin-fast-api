"""Expose only the secret-authenticated bot login route through the preview gate.

Run with sudo on the Hoviat staging VPS. Does not register a Telegram webhook,
start queue workers, change application secrets, or edit production vhosts.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys

SITE = Path('/etc/nginx/sites-available/hoviat-sns-stage')
ENABLED = Path('/etc/nginx/sites-enabled/hoviat-sns-stage')
BACKUP = SITE.with_name('hoviat-sns-stage.before-login-worker-20261027')
TEMP = SITE.with_name('hoviat-sns-stage.login-worker-new')
RELEASE = Path('/home/bardia/apps/sns-staging/releases/20261021-01/backend')
ANCHOR = '''    server_name sns-admin-stage.185.202.113.95.nip.io;
    include /etc/nginx/snippets/hoviat-sns-stage-20261022.conf;'''
ROUTE = '''
    # Login Worker uses its own Bearer secret, not the browser preview password.
    location = /api/sns/auth/bot/request-login {
        auth_basic off;
        limit_except POST { deny all; }
        client_max_body_size 16k;
        proxy_pass http://127.0.0.1:18753;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 3s;
        proxy_read_timeout 15s;
    }
'''


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value)


def main():
    if (sys.argv[1:] or os.geteuid() != 0 or socket.gethostname() != 'srv5089629844'
            or Path(__file__).resolve().parents[2] != RELEASE):
        raise SystemExit('Run with sudo in the approved Hoviat staging release only.')
    if (SITE.is_symlink() or not SITE.is_file() or SITE.resolve() != SITE
            or SITE.stat().st_uid != 0 or ENABLED.resolve() != SITE):
        raise SystemExit('Unexpected staging site file or enabled-site target; stop and review.')
    old = SITE.read_text()
    if ROUTE in old:
        print('Staging login Worker route is already configured. No changes made.')
        return
    if old.count(ANCHOR) != 1 or '/api/sns/auth/bot/request-login' in old:
        raise SystemExit('Staging configuration differs from the expected checkpoint; stop and review.')
    if BACKUP.exists() or BACKUP.is_symlink() or TEMP.exists() or TEMP.is_symlink():
        raise SystemExit('An earlier route setup attempt exists; stop and review before retrying.')
    subprocess.run(['/usr/sbin/nginx', '-t'], check=True)
    write_new(BACKUP, old)
    write_new(TEMP, old.replace(ANCHOR, ANCHOR + ROUTE, 1))
    try:
        TEMP.replace(SITE)
        subprocess.run(['/usr/sbin/nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    except BaseException:
        SITE.write_text(old)
        os.chmod(SITE, 0o600)
        subprocess.run(['/usr/sbin/nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        raise
    print('Staging bot-login route ready; backend Bearer-secret authentication remains required.')
    print('Other preview routes and production configuration were not changed.')
    print('Telegram webhook and channel workers were not changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit('Staging route setup stopped. Share the error above; do not rerun or delete the backup.') from None
