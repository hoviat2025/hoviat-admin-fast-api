"""The SNS deployment must expose both account and business discovery APIs."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


class SNSApplicationRoutesTests(unittest.TestCase):
    def test_sns_mode_mounts_consumer_routes_without_admin(self):
        # Import the actual composition root in isolation without entering its
        # lifespan: registration must work, but workers/storage must not start.
        script = f"""
import sys
sys.path[:] = {sys.path!r}
from unittest.mock import patch
with patch('logging.basicConfig'):
    from app.main import app
paths = {{route.path for route in app.routes}}
required = {{
    '/api/services/services/', '/api/services/services/locations/',
    '/api/services/services/categories/', '/api/services/services/{{service_id}}/',
    '/api/sns/me/services', '/api/sns/me/services/{{service_id}}',
    '/api/sns/me/service-bookmarks', '/api/sns/account/privacy',
}}
assert required <= paths, required - paths
assert not any(path.startswith('/api/admin') for path in paths)
"""
        environment = dict(os.environ, APP_MODE="sns", DISABLE_BACKGROUND_WORKERS="true")
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1], env=environment,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
