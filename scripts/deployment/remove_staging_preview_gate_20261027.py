"""Remove only the extra Nginx browser password from both SNS staging panels."""
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile

SITE = Path('/etc/nginx/sites-available/hoviat-sns-stage')
SNIPPET = Path('/etc/nginx/snippets/hoviat-sns-stage-20261022.conf')
ENABLED = Path('/etc/nginx/sites-enabled/hoviat-sns-stage')
BACKUPS = Path('/home/bardia/apps/sns-staging/private-backups')
RELEASE = Path('/home/bardia/apps/sns-staging/releases/20261021-01/backend')


def atomic(path, content):
    info = path.stat()
    fd, name = tempfile.mkstemp(prefix='.preview-removal-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), info.st_mode & 0o777)
            os.fchown(stream.fileno(), info.st_uid, info.st_gid)
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def nginx_test():
    subprocess.run(['/usr/sbin/nginx', '-t'], check=True)


def main():
    os.umask(0o077)
    if (os.geteuid() != 0 or socket.gethostname() != 'srv5089629844'
            or Path(__file__).resolve().parents[2] != RELEASE):
        raise SystemExit('Run with sudo from the approved Hoviat staging release only.')
    for path in (SITE, SNIPPET):
        if path.is_symlink() or path.resolve() != path or not path.is_file() or path.stat().st_uid != 0:
            raise SystemExit('Unexpected staging configuration file; stopped.')
    if ENABLED.resolve() != SITE:
        raise SystemExit('Unexpected enabled staging site; stopped.')
    old_site, old_snippet = SITE.read_text(), SNIPPET.read_text()
    if (str(SNIPPET) not in old_site or 'sns-admin-stage.185.202.113.95.nip.io' not in old_site
            or 'sns-stage.185.202.113.95.nip.io' not in old_site):
        raise SystemExit('Not the expected isolated staging configuration; stopped.')
    new_site = re.sub(
        r'(?m)^map \$cookie_hoviat_sns_stage_preview \$hoviat_stage_realm \{\n[\s\S]*?^\}\n?',
        '', old_site,
    ).replace('# Isolated SNS staging only. Cookie token is a secret; do not paste this file.',
              '# Isolated SNS staging. Extra browser preview password removed.')
    new_snippet = re.sub(r'(?m)^[ \t]*auth_basic(?:_user_file)?[ \t]+[^;\n]+;[ \t]*\n?', '', old_snippet)
    new_snippet = re.sub(
        r'(?m)^[ \t]*add_header Set-Cookie "hoviat_sns_stage_preview=[^\n]*\n?', '', new_snippet,
    )
    new_snippet = new_snippet.replace(
        '# Only this authenticated static response issues the preview cookie.\n'
        '# Do not put this Set-Cookie header at server level or add `always`.\n',
        '# Compatibility entry URL: still redirects old preview links to the panel.\n',
    )
    if '$hoviat_stage_realm' in new_site + new_snippet or '$cookie_hoviat_sns_stage_preview' in new_site:
        raise SystemExit('Unrecognized preview gate configuration; stopped before writing.')
    nginx_test()
    if (new_site, new_snippet) == (old_site, old_snippet):
        print('The extra staging browser password is already removed.')
        return
    if BACKUPS.is_symlink() or BACKUPS.resolve() != BACKUPS or BACKUPS.stat().st_uid != 0:
        raise SystemExit('Unexpected private backup directory; stopped.')
    backup = Path(tempfile.mkdtemp(prefix='preview-gate-removal-', dir=BACKUPS))
    for name, content in (('nginx.conf', old_site), ('snippet.conf', old_snippet)):
        target = backup / name
        target.write_text(content)
        os.chmod(target, 0o600)
    print('Private configuration backup: ' + str(backup), flush=True)
    try:
        atomic(SITE, new_site)
        atomic(SNIPPET, new_snippet)
        nginx_test()
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    except BaseException:
        atomic(SITE, old_site)
        atomic(SNIPPET, old_snippet)
        nginx_test()
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        raise
    print('Removed browser password gate from BOTH staging panels.')
    print('Admin login and Worker API-secret authentication remain unchanged.')
    print('Production, database, R2 and queue-worker settings were not changed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit('Preview removal stopped; keep the backup and share the error above.') from None
