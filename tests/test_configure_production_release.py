"""Offline production preparation checks; all writes stay in temporary folders."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.deployment import configure_production_release_20261029 as setup


class ProductionReleaseEnvironmentTests(unittest.TestCase):
    def setUp(self):
        source = (Path(__file__).resolve().parents[1] / 'app/core/config.py').read_text(encoding='utf-8')
        self.required = setup.required_settings(source)
        self.values = {key: 'preserved_' + key for key in self.required}
        self.values.update(setup.IDS)
        self.values.update({
            'DATABASE_URL': 'postgresql+asyncpg://hoviat:p%40ss@127.0.0.1:5432/hoviat',
            'R2_ENDPOINT_URL': 'https://example.r2.cloudflarestorage.com',
            'PROFILE_MEDIA_URL': 'https://media.example.test',
            'SECRET_KEY': "quote'back\\slash\\\\end\"$cash",
            'LOGIN_BOT_API_SECRET': "login'\\secret$",
            'APP_MODE': 'all',
        })
        self.backend = setup.updated_text('# Keep the production comment.\n', self.values)
        self.consumer = "# Keep consumer settings.\nSNS_INTERNAL_KEY='old-private-key'\nSNS_SEARCH_TTL=30\nSNS_API_BASE=https://old.example.test/api/sns\nSNS_DEV_LOGIN_ORIGIN=https://sns-stage.example.test\nSNS_USE_MOCK=1\n"
        self.admin = '# Keep admin settings.\nVITE_API_URL=http://127.0.0.1:18753/api\n'
        self.process = setup.parse_env(self.backend)

    def plan(self, backend=None, process=None):
        index = iter(range(10))
        return setup.build_plan(backend or self.backend, self.consumer, self.admin,
                                self.process if process is None else process, self.required,
                                token_factory=lambda size: 'offline_secret_' + str(next(index)))

    def test_pure_plan_preserves_credentials_comments_and_round_trips_quotes(self):
        with patch.object(setup.os, 'open', side_effect=AssertionError('Planning must not write')):
            plan = self.plan()
        prepared = setup.parse_env(plan['backend'])
        for key in self.required:
            self.assertEqual(prepared[key], self.values[key])
        self.assertIn('# Keep the production comment.', plan['backend'])
        self.assertIn('# Keep consumer settings.', plan['consumer'])
        self.assertIn('# Keep admin settings.', plan['admin'])
        worker = setup.parse_env(plan['worker'])
        self.assertEqual(worker['LOGIN_API_SECRET'], self.values['LOGIN_BOT_API_SECRET'])
        self.assertEqual(worker['SENDER_API_SECRET'], prepared['SENDER_WEBHOOK_API_SECRET'])
        self.assertNotEqual(worker['SENDER_WEBHOOK_SECRET'], worker['LOGIN_WEBHOOK_SECRET'])

    def test_production_flags_and_frontend_targets_replace_staging_or_mock_defaults(self):
        plan = self.plan()
        prepared = setup.parse_env(plan['backend'])
        for key, value in setup.FLAGS.items():
            self.assertEqual(prepared[key], value)
        self.assertEqual(prepared['SERVICE_MEDIA_URL'], self.values['PROFILE_MEDIA_URL'])
        consumer = setup.parse_env(plan['consumer'])
        self.assertEqual(consumer['SNS_API_BASE'], 'http://127.0.0.1:8000/api/sns')
        self.assertEqual(consumer['SERVICES_API_BASE'], 'http://127.0.0.1:8000/api/services')
        self.assertEqual(consumer['SNS_USE_MOCK'], '0')
        self.assertEqual(consumer['SNS_DEV_LOGIN_ORIGIN'], '')
        self.assertEqual(consumer['NEXT_PUBLIC_BOT_USERNAME'], 'hoviatloginbot')
        self.assertEqual(consumer['SNS_INTERNAL_KEY'], 'old-private-key')
        self.assertEqual(consumer['SNS_SEARCH_TTL'], '30')
        self.assertEqual(setup.parse_env(plan['admin'])['VITE_API_URL'], 'https://185.202.113.95.nip.io/api')

    def test_missing_or_different_process_credentials_refuse_without_values(self):
        for value in (None, 'different'):
            process = dict(self.process)
            if value is None:
                process.pop('SECRET_KEY')
            else:
                process['SECRET_KEY'] = value
            with self.assertRaises(setup.Refused) as caught:
                self.plan(process=process)
            self.assertNotIn(self.values['SECRET_KEY'], str(caught.exception))

    def test_staging_database_and_test_channels_refuse_even_if_process_matches(self):
        for key, value in [('DATABASE_URL', 'postgresql://hoviat:pass@127.0.0.1/hoviat_admin_test'),
                           ('MAIN_CHANNEL_ID', '-1003941932759')]:
            changed = setup.updated_text(self.backend, {key: value})
            with self.assertRaises(setup.Refused):
                self.plan(backend=changed, process=setup.parse_env(changed))

    def test_process_only_signing_override_requires_review(self):
        process = {**self.process, 'ALGORITHM': 'HS512'}
        with self.assertRaises(setup.Refused):
            self.plan(process=process)

    def test_existing_sender_api_password_is_preserved(self):
        changed = setup.updated_text(self.backend, {'SENDER_WEBHOOK_API_SECRET': 'keep_this_existing_value'})
        plan = self.plan(backend=changed, process=setup.parse_env(changed))
        self.assertEqual(setup.parse_env(plan['backend'])['SENDER_WEBHOOK_API_SECRET'], 'keep_this_existing_value')
        self.assertEqual(setup.parse_env(plan['worker'])['SENDER_API_SECRET'], 'keep_this_existing_value')

    def test_required_keys_are_discovered_without_importing_settings(self):
        self.assertEqual(setup.required_settings('class Settings:\n    SECRET: str\n    OPTIONAL: bool = False\n'), {'SECRET'})

    def test_new_files_only_and_rerun_refuses_without_losing_passwords(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            release = base / 'release'
            for project in ('backend', 'consumer', 'admin'):
                (release / project).mkdir(parents=True)
            private = base / 'private'
            plan = self.plan()
            setup.write_plan(plan, release, private)
            paths = [release / 'backend/.env', release / 'consumer/.env.local', release / 'admin/.env.production', private / 'worker-settings-20261029.env']
            originals = [path.read_bytes() for path in paths]
            with self.assertRaises(setup.Refused):
                setup.write_plan(self.plan(), release, private)
            self.assertEqual([path.read_bytes() for path in paths], originals)
            if setup.sys.platform == 'linux':
                self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in paths))

    def test_existing_candidate_env_refuses_before_any_other_file_is_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            release = base / 'release'
            for project in ('backend', 'consumer', 'admin'):
                (release / project).mkdir(parents=True)
            existing = release / 'consumer/.env.local'
            existing.write_text('KEEP=existing\n', encoding='utf-8')
            with self.assertRaises(setup.Refused):
                setup.write_plan(self.plan(), release, base / 'private')
            self.assertEqual(existing.read_text(encoding='utf-8'), 'KEEP=existing\n')
            self.assertFalse((release / 'backend/.env').exists())
            self.assertFalse((base / 'private').exists())
