"""Local impersonation is explicit, isolated, revocable and queues no Telegram work."""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.core.security import create_access_token
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.auth.dependencies import get_dev_login_service
from app.modules.sns.auth.router import router
from app.modules.sns.auth.services.dev_login import DevLoginService, _dev_token, dev_token_secret
from app.modules.sns.rate_limit import login_rate_limit


def config(**changes):
    values = dict(
        DEV_LOGIN_ENABLED=True, DEV_LOGIN_USER_ID=-900000001,
        DISABLE_BACKGROUND_WORKERS=True,
        DATABASE_URL="postgresql+asyncpg://local:test@127.0.0.1:5433/local_test",
        ACCESS_TOKEN_EXPIRE_MINUTES=37, SECRET_KEY="dev-login-unit-secret",
        ALGORITHM="HS256",
    )
    return SimpleNamespace(**(values | changes))


def user(**changes):
    values = dict(
        user_id=-900000001, mode="sns_dev", nickname="Local developer", username=None,
        is_ban=False, is_in_eurobot=False, is_in_hilfen_bot=False,
    )
    return SimpleNamespace(**(values | changes))


def local_request(*, peer="127.0.0.1", host="127.0.0.1", origin=None):
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request({
        "type": "http", "method": "GET", "scheme": "http", "path": "/api/sns/account/me",
        "query_string": b"", "headers": headers, "client": (peer, 50000), "server": (host, 80),
    })


class DevLoginTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(
            execute=AsyncMock(), scalar=AsyncMock(return_value=user()),
            commit=AsyncMock(), rollback=AsyncMock(),
        )
        self.service = DevLoginService(self.db)
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(router, prefix="/api/sns/auth")
        self.app.dependency_overrides[get_dev_login_service] = lambda: self.service
        self.app.dependency_overrides[login_rate_limit] = lambda: None

    async def request(self, method="POST", *, peer="127.0.0.1", host="127.0.0.1", **kwargs):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, client=(peer, 50000)),
            base_url="http://" + host,
        ) as client:
            return await client.request(method, "/api/sns/auth/dev-login", **kwargs)

    def test_dev_login_is_disabled_by_default_and_uses_a_synthetic_id(self):
        self.assertIs(Settings.model_fields["DEV_LOGIN_ENABLED"].default, False)
        self.assertLess(Settings.model_fields["DEV_LOGIN_USER_ID"].default, 0)

    async def test_disabled_and_unsafe_configuration_returns_404_before_database_work(self):
        cases = [
            {"DEV_LOGIN_ENABLED": False},
            {"DISABLE_BACKGROUND_WORKERS": False},
            {"DATABASE_URL": "postgresql+asyncpg://local:test@remote.example/prod"},
            {"DATABASE_URL": "sqlite:///local.db"},
            {"DATABASE_URL": "malformed"},
            {"DEV_LOGIN_USER_ID": 12345},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                with patch("app.modules.sns.auth.services.dev_login.settings", config(**changes)):
                    for method in ("GET", "POST"):
                        response = await self.request(method)
                        self.assertEqual(response.status_code, 404, response.text)
        self.db.execute.assert_not_awaited()
        self.db.scalar.assert_not_awaited()

    async def test_forwarded_headers_cannot_enable_remote_login(self):
        with patch("app.modules.sns.auth.services.dev_login.settings", config()):
            for changes in (
                {"peer": "203.0.113.4", "headers": {"X-Forwarded-For": "127.0.0.1"}},
                {"host": "public.example", "headers": {"X-Forwarded-Host": "localhost"}},
            ):
                response = await self.request(**changes)
                self.assertEqual(response.status_code, 404)
        self.db.execute.assert_not_awaited()

    async def test_capability_is_local_and_does_not_create_a_session(self):
        with patch("app.modules.sns.auth.services.dev_login.settings", config()):
            response = await self.request("GET")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"enabled": True})
        self.db.execute.assert_not_awaited()

    async def test_remote_null_and_malformed_browser_origins_are_rejected(self):
        with patch("app.modules.sns.auth.services.dev_login.settings", config()):
            for origin in (
                "https://remote.example", "null", "not-a-url",
                "http://localhost:invalid", "file://localhost",
                "http://user:pass@localhost", "http://localhost/path",
            ):
                with self.subTest(origin=origin):
                    response = await self.request(headers={"Origin": origin})
                    self.assertEqual(response.status_code, 404, response.text)
        self.db.execute.assert_not_awaited()

    async def test_local_browser_origin_may_use_a_different_port(self):
        with patch("app.modules.sns.auth.services.dev_login.settings", config()):
            for origin in ("http://localhost:18745", "http://127.0.0.1:18745", "https://[::1]:18745"):
                response = await self.request("GET", headers={"Origin": origin})
                self.assertEqual(response.status_code, 200, response.text)
        self.db.execute.assert_not_awaited()

    async def test_client_cannot_request_admin_role_extra_fields_or_invalid_ids(self):
        with patch("app.modules.sns.auth.services.dev_login.settings", config()):
            for payload in (
                {"role": "admin"}, {"token": "ignored"}, {"user_id": True},
                {"user_id": 1.5}, {"user_id": "123x"}, {"user_id": 2**63},
            ):
                response = await self.request(json=payload)
                self.assertEqual(response.status_code, 422, response.text)
        self.db.execute.assert_not_awaited()
        self.db.scalar.assert_not_awaited()

    async def test_explicit_existing_local_user_gets_marked_sns_session_without_upsert_or_jobs(self):
        local = config()
        self.db.scalar.return_value = user(user_id=123, mode=None, nickname="Chosen local user")
        with (
            patch("app.modules.sns.auth.services.dev_login.settings", local),
            patch("app.shared.repositories.job_queue.JobQueueRepository.enqueue_medium_priority", AsyncMock()) as queue,
        ):
            response = await self.request(json={"user_id": 123})
            self.assertEqual(response.status_code, 200, response.text)
            claims = jwt.decode(response.json()["data"]["access_token"], dev_token_secret(), algorithms=[local.ALGORITHM])
        self.assertEqual(response.json()["data"]["user_id"], 123)
        self.assertEqual(claims["sub"], "123")
        self.assertEqual(claims["role"], "sns_user")
        self.assertIs(claims["dev_login"], True)
        self.assertEqual(self.db.execute.await_count, 1)
        self.assertIn("user_privacy_settings", str(self.db.execute.await_args.args[0]))
        lookup = str(self.db.scalar.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("users_eurobot.user_id = 123", lookup)
        self.assertIn("FOR UPDATE", lookup)
        queue.assert_not_awaited()

    async def test_explicit_missing_local_user_is_not_created(self):
        self.db.scalar.return_value = None
        with patch("app.modules.sns.auth.services.dev_login.settings", config()):
            response = await self.request(json={"user_id": 123})
        self.assertEqual(response.status_code, 404)
        self.db.execute.assert_not_awaited()
        self.db.commit.assert_not_awaited()
        self.db.rollback.assert_awaited_once()

    async def test_success_uses_same_sns_session_with_configured_expiry_and_no_jobs(self):
        local = config()
        with (
            patch("app.modules.sns.auth.services.dev_login.settings", local),
            patch("app.core.security.settings", local),
            patch("app.modules.sns.auth.services.post_login.finalize_login", AsyncMock()) as finalize,
            patch("app.shared.repositories.job_queue.JobQueueRepository.enqueue_medium_priority", AsyncMock()) as queue,
        ):
            response = await self.request()
            signing_key = dev_token_secret()
        self.assertEqual(response.status_code, 200, response.text)
        session = response.json()["data"]
        self.assertEqual(session["user_id"], local.DEV_LOGIN_USER_ID)
        self.assertEqual(session["token_type"], "bearer")
        claims = jwt.decode(session["access_token"], signing_key, algorithms=[local.ALGORITHM])
        self.assertEqual(claims["sub"], str(local.DEV_LOGIN_USER_ID))
        self.assertEqual(claims["role"], "sns_user")
        self.assertIs(claims["dev_login"], True)
        with self.assertRaises(JWTError):
            jwt.decode(session["access_token"], local.SECRET_KEY, algorithms=[local.ALGORITHM])
        self.assertAlmostEqual(claims["exp"] - time.time(), 37 * 60, delta=3)
        self.db.commit.assert_awaited_once()
        self.db.rollback.assert_not_awaited()
        finalize.assert_not_awaited()
        queue.assert_not_awaited()
        user_insert = self.db.execute.await_args_list[0].args[0]
        self.assertIn("ON CONFLICT (user_id) DO NOTHING", str(user_insert.compile(dialect=postgresql.dialect())))
        self.assertEqual(user_insert.compile().params["user_id"], local.DEV_LOGIN_USER_ID)
        privacy_insert = self.db.execute.await_args_list[1].args[0]
        self.assertIn("user_privacy_settings", str(privacy_insert))
        self.assertIn("DO NOTHING", str(privacy_insert))

    async def test_identity_collision_ban_or_bot_identity_is_not_overwritten(self):
        for existing, expected_status in (
            (user(mode="real"), 409), (user(is_ban=True), 403),
            (user(is_in_eurobot=True), 409), (user(is_in_hilfen_bot=True), 409),
        ):
            with self.subTest(existing=existing):
                self.db.scalar.return_value = existing
                with patch("app.modules.sns.auth.services.dev_login.settings", config()):
                    response = await self.request()
                self.assertEqual(response.status_code, expected_status)
        self.db.commit.assert_not_awaited()
        self.assertEqual(self.db.rollback.await_count, 4)

    async def test_disabling_dev_login_revokes_existing_dev_tokens_only(self):
        local = config()
        with patch("app.core.security.settings", local):
            token = create_access_token({"sub": str(local.DEV_LOGIN_USER_ID), "role": "sns_user"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with (
            patch("app.modules.sns.dependencies.settings", local),
            patch("app.modules.sns.auth.services.dev_login.settings", config(DEV_LOGIN_ENABLED=False)),
            patch("app.modules.sns.dependencies.UserBaseRepository.get_by_id", AsyncMock(return_value=user())) as lookup,
        ):
            with self.assertRaises(HTTPException) as caught:
                await get_current_sns_user(request=local_request(), credentials=credentials, db=self.db)
            self.assertEqual(caught.exception.status_code, 401)
            # A normal SNS identity is not revoked by the development toggle.
            lookup.return_value = user(mode=None)
            result = await get_current_sns_user(request=local_request(), credentials=credentials, db=self.db)
            self.assertIsNone(result.mode)

    async def test_existing_user_impersonation_token_requires_local_request_and_enabled_guards(self):
        local = config()
        with patch("app.modules.sns.auth.services.dev_login.settings", local):
            token = _dev_token(123)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with (
            patch("app.modules.sns.dependencies.settings", local),
            patch("app.modules.sns.dependencies.UserBaseRepository.get_by_id", AsyncMock(return_value=user(user_id=123, mode=None))) as lookup,
        ):
            with patch("app.modules.sns.auth.services.dev_login.settings", local):
                result = await get_current_sns_user(request=local_request(), credentials=credentials, db=self.db)
                self.assertEqual(result.user_id, 123)
                for request in (
                    local_request(peer="203.0.113.4"), local_request(host="public.example"),
                    local_request(origin="https://remote.example"),
                ):
                    lookup.reset_mock()
                    with self.assertRaises(HTTPException) as caught:
                        await get_current_sns_user(request=request, credentials=credentials, db=self.db)
                    self.assertEqual(caught.exception.status_code, 401)
                    lookup.assert_not_awaited()
            for changes in (
                {"DEV_LOGIN_ENABLED": False}, {"DISABLE_BACKGROUND_WORKERS": False},
                {"DATABASE_URL": "postgresql+asyncpg://local:test@remote.example/stage"},
            ):
                lookup.reset_mock()
                with patch("app.modules.sns.auth.services.dev_login.settings", config(**changes)):
                    with self.assertRaises(HTTPException) as caught:
                        await get_current_sns_user(request=local_request(), credentials=credentials, db=self.db)
                    self.assertEqual(caught.exception.status_code, 401)
                lookup.assert_not_awaited()

    async def test_dev_marker_cannot_be_accepted_under_the_normal_signing_key(self):
        local = config()
        with patch("app.core.security.settings", local):
            token = create_access_token({"sub": "123", "role": "sns_user", "dev_login": True})
        with (
            patch("app.modules.sns.dependencies.settings", local),
            patch("app.modules.sns.auth.services.dev_login.settings", local),
            patch("app.modules.sns.dependencies.UserBaseRepository.get_by_id", AsyncMock()) as lookup,
        ):
            with self.assertRaises(HTTPException) as caught:
                await get_current_sns_user(request=local_request(), credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db=self.db)
            self.assertEqual(caught.exception.status_code, 401)
            lookup.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
