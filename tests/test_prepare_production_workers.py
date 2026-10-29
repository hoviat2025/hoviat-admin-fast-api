"""Private Worker rendering without real tokens, network or live paths."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.deployment import prepare_production_workers_20261029 as prep


class ProductionWorkerPreparationTests(unittest.TestCase):
    def setUp(self):
        self.live = {key: 'fake_' + key for key in (
            'DATABASE_URL', 'SECRET_KEY', 'SENDER_BOT_TOKEN',
            'SNS_LOGIN_BOT_TOKEN', 'LOGIN_BOT_API_SECRET')}
        self.candidate = {**self.live, 'SENDER_WEBHOOK_API_SECRET': 'a' * 43}

    def test_saved_credentials_are_reused_without_rotation(self):
        initial = prep.worker_settings(self.candidate, self.live)
        self.assertEqual(prep.worker_settings(self.candidate, self.live, initial), initial)
        self.assertNotEqual(initial['sender_webhook_secret'], initial['login_webhook_secret'])

    def test_changed_credentials_and_weak_secret_are_refused(self):
        for key, value in (('SECRET_KEY', 'changed'), ('SENDER_WEBHOOK_API_SECRET', 'short')):
            with self.assertRaises(prep.Refused):
                prep.worker_settings({**self.candidate, key: value}, self.live)

    def test_templates_are_filled_with_escaped_literals_and_production_origins(self):
        folder = Path(__file__).resolve().parents[1] / 'scripts/cloudflare-workers'
        settings = prep.worker_settings(self.candidate, self.live)
        settings['login_api_secret'] = 'quote"slash\\newline\n'
        sender, login = prep.render_workers(
            (folder / 'sender-bot-webhook.js').read_text(encoding='utf-8'),
            (folder / 'sns-login-bot-production.js').read_text(encoding='utf-8'), settings)
        self.assertIn('const API_SECRET = ' + json.dumps(settings['sender_api_secret']) + ';', sender)
        self.assertIn('  API_SECRET: ' + json.dumps(settings['login_api_secret']) + ',', login)
        self.assertIn('https://185.202.113.95.nip.io', sender)
        self.assertIn('https://app.185.202.113.95.nip.io/login', login)
        self.assertNotIn('const WEBHOOK_SECRET = "";', sender)

    def test_rendering_refuses_unexpected_template(self):
        with self.assertRaises(prep.Refused):
            prep.render_workers('wrong template', '', prep.worker_settings(self.candidate, self.live))

    def test_private_files_are_idempotent_and_manual_edits_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'worker.js'
            prep.save_private(path, 'first')
            prep.save_private(path, 'first')
            with self.assertRaises(prep.Refused):
                prep.save_private(path, 'different')
            self.assertEqual(path.read_text(), 'first')

    def test_earlier_env_secrets_are_reused_and_conflicting_sources_refused(self):
        settings = prep.worker_settings(self.candidate, self.live)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            legacy, metadata = folder / 'old.env', folder / 'settings.json'
            legacy.write_text(''.join(f'{key.upper()}={value}\n' for key, value in settings.items()))
            self.assertEqual(prep.saved_settings(metadata, legacy), settings)
            metadata.write_text(json.dumps(settings))
            self.assertEqual(prep.saved_settings(metadata, legacy), settings)
            metadata.write_text(json.dumps({**settings, 'sender_webhook_secret': 'different'}))
            with self.assertRaises(prep.Refused):
                prep.saved_settings(metadata, legacy)
