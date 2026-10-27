"""One-shot approved staging Telegram preparation; run manually on the VPS.

The staging API and web app are briefly offline. Failures after stopping leave
both stopped for inspection; private backups are retained. Never run on production.
"""
import getpass
import io
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from dotenv import dotenv_values
from enable_staging_features_20261027 import (
    BACKEND, BACKEND_ENV, CONSUMER_ENV, BACKUPS, PRODUCTION, SITE, ENABLED,
    atomic_env, read_env, replace_settings, make_url, regular, check_service_and_gate,
)
from expose_staging_login_worker_20261027 import ROUTE, ANCHOR
from configure_staging_sender_worker_20261027 import PATHS

DROPIN = Path('/etc/systemd/system/hoviat-sns-stage-api.service.d/40-telegram-test.conf')
SQL = Path(__file__).with_name('reset_staging_telegram_20261027.sql')
SERVICES = ['hoviat-sns-stage-api.service', 'hoviat-sns-stage-web.service']
IDS = dict(MAIN_CHANNEL_ID='-1003941932759', MAIN_GROUP_ID='-1003741849641',
           PUBLIC_CHANNEL_ID='-1003997195070', PUBLIC_GROUP_ID='-1003915100291',
           HILFEN_CHANNEL_ID='-1003872442653', HILFEN_GROUP_ID='-1003946251854')
FLAGS = dict(APP_MODE='all', DISABLE_BACKGROUND_WORKERS='false',
             TELEGRAM_API_ENABLED='true', DEV_LOGIN_ENABLED='false',
             TELEGRAM_BASE_URL='https://api.telegram.org')
phase, backup, stopped = 'preflight', None, False


class Refused(Exception):
    """Static public diagnostics only."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


HTTP = build_opener(NoRedirect)
# workers.dev Browser Integrity Check can reject Python's library-default UA
# with 1010 before the request reaches our Worker. Identify this client honestly.
HTTP.addheaders = [('User-Agent', 'Hoviat-Staging-Setup/1.0')]


def run(args, **kwargs):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True,
                              timeout=kwargs.pop('timeout', 30), **kwargs)
    except subprocess.CalledProcessError as error:
        if backup is not None:
            # Keep diagnostic output private; never print a subprocess command
            # or its environment, since these can include sensitive settings.
            log = backup / (re.sub(r'[^a-z0-9]+', '-', phase.lower()) + '.log')
            log.write_text((error.stdout or '') + '\n' + (error.stderr or ''))
            os.chmod(log, 0o600)
            print('Private diagnostic log: ' + str(log), file=sys.stderr)
        raise


def post(url, payload, headers=None):
    request = Request(url, json.dumps(payload).encode(),
                      {'Content-Type': 'application/json', **(headers or {})}, method='POST')
    try:
        with HTTP.open(request, timeout=12) as response:
            return response.status, response.read(1048576)
    except HTTPError as error:
        error.close()
        return error.code, b''


def telegram(token, method, payload=None):
    status, body = post('https://api.telegram.org/bot' + token + '/' + method, payload or {})
    if status != 200:
        raise Refused('Telegram verification or webhook registration failed; inspect bot configuration privately.')
    result = json.loads(body)
    if result.get('ok') is not True:
        raise Refused('Telegram did not accept the requested operation.')
    return result['result']


def disabled(value):
    return not value or bool(re.search(r'disabl|placeholder|changeme|replace|dummy|example', value, re.I))


def token_value(values, key):
    value = (values.get(key) or '').strip()
    if disabled(value):
        value = getpass.getpass('Enter test ' + key + ': ').strip()
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', value):
        raise Refused('A valid test bot token is required.')
    return value


def worker_url(label, default=''):
    value = input(label + (' [Enter for ' + default + ']' if default else '') + ': ').strip() or default
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.workers.dev')
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or any(ord(c) <= 32 for c in value)):
        raise Refused('Worker URL must be HTTPS on workers.dev without credentials, query or fragment.')
    return value


def worker_secret(label):
    value = getpass.getpass(label + ' deployed WEBHOOK_SECRET: ')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', value):
        raise Refused('Worker WEBHOOK_SECRET must use Telegram secret-token characters.')
    if value != getpass.getpass('Repeat ' + label + ' WEBHOOK_SECRET: '):
        raise Refused('Worker secret entries did not match.')
    return value


def main():
    global phase, backup, stopped
    os.umask(0o077)
    if (sys.argv[1:] or sys.platform != 'linux' or os.geteuid() != 0
            or socket.gethostname() != 'srv5089629844'
            or Path(__file__).absolute().resolve() != Path(__file__).absolute()
            or Path(__file__).absolute().parents[2] != BACKEND
            or Path.cwd() != BACKEND or Path(sys.prefix).absolute() != BACKEND / '.venv'):
        raise Refused('Run with sudo from the exact approved staging release using its .venv/bin/python.')
    if DROPIN.exists() or DROPIN.is_symlink():
        raise Refused('Telegram setup already has a drop-in; inspect the previous attempt before resetting again.')
    if DROPIN.parent.exists() and (DROPIN.parent.resolve() != DROPIN.parent
            or not DROPIN.parent.is_dir() or DROPIN.parent.stat().st_uid != 0):
        raise Refused('Systemd drop-in directory must be a real root-owned directory.')
    check_service_and_gate()
    regular(SQL)
    original, values = read_env(BACKEND_ENV)
    consumer_original, consumer = read_env(CONSUMER_ENV)
    database = make_url(values.get('DATABASE_URL') or '')
    if (values.get('APP_MODE') != 'all' or database.drivername not in ('postgresql', 'postgresql+asyncpg')
            or database.host != '127.0.0.1' or database.port != 5432
            or database.username != 'hoviat_sns_stage' or database.database != 'hoviat_sns_stage_20261021'
            or database.query):
        raise Refused('APP_MODE or the isolated staging database settings do not match the approved target.')
    if (consumer.get('SNS_API_BASE') != 'http://127.0.0.1:18753/api/sns'
            or consumer.get('SERVICES_API_BASE') != 'http://127.0.0.1:18753/api/services'):
        raise Refused('Consumer must use the approved staging loopback API.')
    if any(not (values.get(key) or '').strip() for key in ('LOGIN_BOT_API_SECRET', 'SENDER_WEBHOOK_API_SECRET')):
        raise Refused('Existing staging login and sender API secrets must be configured first.')
    print('1/6: Checking the two test bot identities (tokens are not printed).', flush=True)
    login, sender = (token_value(values, key) for key in ('SNS_LOGIN_BOT_TOKEN', 'SENDER_BOT_TOKEN'))
    _, production = read_env(PRODUCTION)
    production_ids = {v.split(':', 1)[0] for k, v in production.items()
                      if k in ('EURO_BOT_TOKEN', 'HILFEN_BOT_TOKEN', 'SNS_LOGIN_BOT_TOKEN', 'SENDER_BOT_TOKEN')
                      and v and re.match(r'^\d+:', v)}
    if login.split(':')[0] == sender.split(':')[0] or any(t.split(':')[0] in production_ids for t in (login, sender)):
        raise Refused('Two different test bots are required; neither may belong to production.')
    bots = [telegram(t, 'getMe') for t in (login, sender)]
    if any(not b.get('is_bot') or not b.get('username') for b in bots):
        raise Refused('Both test tokens must identify Telegram bots with usernames.')
    print('2/6: Checking test channels, linked discussions and sender permissions.', flush=True)
    for label in ('MAIN', 'PUBLIC', 'HILFEN'):
        print('Checking ' + label + ' test channel and discussion group.', flush=True)
        try:
            channel, group = (telegram(sender, 'getChat', {'chat_id': IDS[label + suffix]})
                              for suffix in ('_CHANNEL_ID', '_GROUP_ID'))
            if (channel.get('id') != int(IDS[label + '_CHANNEL_ID']) or channel.get('type') != 'channel'
                    or channel.get('linked_chat_id') != int(IDS[label + '_GROUP_ID'])
                    or group.get('id') != int(IDS[label + '_GROUP_ID'])
                    or group.get('type') not in ('group', 'supergroup')):
                raise Refused('invalid chat pair')
            for chat in (channel, group):
                member = telegram(sender, 'getChatMember', {'chat_id': chat['id'], 'user_id': bots[1]['id']})
                if member.get('status') != 'administrator' or (chat is channel and member.get('can_post_messages') is not True):
                    raise Refused('missing administrator permission')
        except Exception:
            raise Refused(label + ' test channel/discussion verification failed; sender needs administrator permissions.') from None
    login_url = worker_url('Login Worker URL', 'https://sns-login-bot-webhook-test.safaee1361.workers.dev/')
    sender_url = worker_url('Sender Worker URL')
    secrets = [worker_secret(label) for label in ('Login Worker', 'Sender Worker')]
    print('3/6: Checking deployed Worker webhook protection; no messages are sent.', flush=True)
    for label, url, secret in zip(('Login', 'Sender'), (login_url, sender_url), secrets):
        without_secret = post(url, {'update_id': 0})[0]
        if without_secret != 401:
            raise Refused(label + ' Worker returned HTTP ' + str(without_secret)
                          + ' without a webhook password; expected 401. No staging changes made.')
        with_secret = post(url, {'update_id': 0}, {'X-Telegram-Bot-Api-Secret-Token': secret})[0]
        if with_secret != 200:
            raise Refused(label + ' Worker returned HTTP ' + str(with_secret)
                          + ' with the webhook password; expected 200. Check the deployed WEBHOOK_SECRET/configuration.')
    old_site = SITE.read_text()
    if SITE.stat().st_uid != 0 or old_site.count(ANCHOR) != 1:
        raise Refused('Unexpected staging Nginx owner or admin server anchor.')
    for path in PATHS:
        position = old_site.find('location = ' + path + ' {')
        block = old_site[position:old_site.find('    }', position) + 5] if position >= 0 else ''
        if not all(text in block for text in ('auth_basic off;', 'proxy_pass http://127.0.0.1:18753;', 'limit_except PUT', 'proxy_set_header Authorization $http_authorization;')):
            raise Refused('The three staging sender callback routes must already be configured.')
    if ROUTE not in old_site and '/api/sns/auth/bot/request-login' in old_site:
        raise Refused('Existing staging login route differs from the approved route.')
    new_site = old_site if ROUTE in old_site else old_site.replace(ANCHOR, ANCHOR + ROUTE, 1)
    run(['/usr/sbin/nginx', '-t'])
    settings = {**IDS, **FLAGS, 'SNS_LOGIN_BOT_TOKEN': login, 'SENDER_BOT_TOKEN': sender}
    for key in ('EURO_BOT_TOKEN', 'HILFEN_BOT_TOKEN'):
        if disabled(values.get(key)):
            settings[key] = login
    updated = replace_settings(original, settings)
    consumer_settings = {'NEXT_PUBLIC_BOT_USERNAME': bots[0]['username']}
    consumer_updated = replace_settings(consumer_original, consumer_settings)
    for previous, content, changes in ((values, updated, settings), (consumer, consumer_updated, consumer_settings)):
        if dict(dotenv_values(stream=io.StringIO(content), interpolate=True)) != {**previous, **changes}:
            raise Refused('Environment serialization would change unrelated settings.')
    if BACKUPS.exists() and (BACKUPS.resolve() != BACKUPS or not BACKUPS.is_dir()
            or BACKUPS.stat().st_uid != 0 or stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700):
        raise Refused('Private backup directory must be root-owned, unlinked and mode 0700.')
    if BACKUPS.parent.resolve() != BACKUPS.parent or DROPIN.parent.parent.resolve() != DROPIN.parent.parent:
        raise Refused('Configuration parent directories must not contain links.')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='telegram-20261027-', dir=BACKUPS))
    for name, path in (('backend.env', BACKEND_ENV), ('consumer.env.local', CONSUMER_ENV), ('nginx.conf', SITE)):
        target = backup / name
        target.write_bytes(path.read_bytes())
        os.chmod(target, 0o600)
        os.chown(target, path.stat().st_uid, path.stat().st_gid)
    print('Private backups: ' + str(backup), flush=True)
    print('4/6: Backing up and clearing staging Telegram state. Staging is briefly offline.', flush=True)
    phase, stopped = 'stop staging services', True
    run(['systemctl', 'stop', *SERVICES])
    phase = 'database snapshot'
    postgres = pwd.getpwnam('postgres')
    dumpdir = Path(tempfile.mkdtemp(prefix='sns-stage-20261027-ready-', dir='/var/lib/postgresql'))
    os.chown(dumpdir, postgres.pw_uid, postgres.pw_gid)
    os.chmod(dumpdir, 0o700)
    dump = dumpdir / 'staging.dump'
    run(['sudo', '-u', 'postgres', 'pg_dump', '--host', '/var/run/postgresql', '--port', '5432',
         '--dbname', 'hoviat_sns_stage_20261021', '--format=custom', '--no-owner', '--no-acl', '--file', str(dump)], timeout=180)
    print('Database snapshot: ' + str(dump), flush=True)
    phase = 'reset staging Telegram state'
    result = run(['sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c role=hoviat_sns_stage', 'psql', '-X',
                  '-v', 'ON_ERROR_STOP=1', '--host', '/var/run/postgresql', '--port', '5432',
                  '--dbname', 'hoviat_sns_stage_20261021'], input=SQL.read_text(), timeout=150)
    print(result.stdout, end='', flush=True)  # The fixed SQL emits aggregate counts only.
    phase = 'write staging configuration'
    atomic_env(BACKEND_ENV, updated, original)
    atomic_env(CONSUMER_ENV, consumer_updated, consumer_original)
    DROPIN.parent.mkdir(mode=0o755, exist_ok=True)
    fd = os.open(DROPIN, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('[Service]\n' + ''.join('Environment="' + k + '=' + v + '"\n' for k, v in FLAGS.items()))
    phase = 'build staging consumer'
    print('5/6: Building the staging frontend; this may take a few minutes.', flush=True)
    run(['sudo', '-u', 'bardia', '/usr/bin/npm', 'run', 'build'], cwd=CONSUMER_ENV.parent, timeout=600)
    phase = 'configure staging Nginx'
    if new_site != old_site:
        atomic_env(SITE, new_site, old_site)
    try:
        run(['/usr/sbin/nginx', '-t'])
        run(['systemctl', 'reload', 'nginx'])
    except BaseException:
        atomic_env(SITE, old_site, new_site)
        run(['/usr/sbin/nginx', '-t'])
        run(['systemctl', 'reload', 'nginx'])
        raise
    phase = 'register test bot webhooks'
    print('6/6: Registering test webhooks and starting staging with posting enabled.', flush=True)
    for token, url, secret, updates in zip((login, sender), (login_url, sender_url), secrets,
                                            (['message', 'callback_query'], ['message'])):
        if telegram(token, 'setWebhook', {'url': url, 'secret_token': secret, 'allowed_updates': updates}) is not True:
            raise Refused('Test webhook registration did not return success.')
    phase = 'start staging services'
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'start', *SERVICES])
    phase = 'staging health verification'
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with HTTP.open('http://127.0.0.1:18753/health', timeout=min(2, max(0.01, deadline - time.monotonic()))) as response:
                if response.status == 200:
                    break
        except Exception:
            pass
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    else:
        raise Refused('Staging API did not become healthy within twenty seconds.')
    if any(run(['systemctl', 'is-active', service]).stdout.strip() != 'active' for service in SERVICES):
        raise Refused('A staging service is not active.')
    stopped = False
    print('Ready: login @' + bots[0]['username'] + '; sender @' + bots[1]['username'])
    print('Login Worker: ' + login_url + '\nSender Worker: ' + sender_url)
    print('Queued workers enabled; Telegram enabled; dev login disabled. Existing shared R2 settings retained.')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        if stopped:
            try:
                run(['systemctl', 'stop', *SERVICES])
            except BaseException:
                pass
        print('STOP during ' + phase + '. ' + (str(error) if isinstance(error, Refused) else 'Setup failed; no error body or traceback is displayed.'), file=sys.stderr)
        if backup:
            print('Private backups: ' + str(backup) + '. Inspect partial changes before retrying. Staging services were requested stopped.', file=sys.stderr)
        sys.exit(1)
