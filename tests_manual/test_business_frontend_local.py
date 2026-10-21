"""Local web smoke fixtures and HTTP checks; never sends Telegram messages.

Run seed, then check with the consumer on 127.0.0.1:18745, then cleanup.
Only the explicitly named local DB is allowed. Synthetic rows are committed so
the separately running servers can see them, and cleanup deletes only those ids.
"""
import argparse
import asyncio
import hashlib
import json
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.category import Category
from app.models.job_queue import JobQueue
from app.models.service import Service
from app.models.sns_login_token import SnsLoginToken
from app.models.user import User
from app.models.user_privacy_settings import UserPrivacySettings
from app.modules.services.schemas.service_requests import ServiceCreateRequest
from app.modules.services.services.service_service import ServiceService

STATE = Path(tempfile.gettempdir()) / "sns-business-web-fixture.json"
FRONTEND = "http://127.0.0.1:18745"


async def guard(db):
    url = make_url(settings.DATABASE_URL)
    assert (url.host, url.port, url.database) == ("127.0.0.1", 5433, "hoviat_service_dev")
    assert settings.DISABLE_BACKGROUND_WORKERS
    assert await db.scalar(text("SELECT current_database()")) == "hoviat_service_dev"


async def seed():
    assert not STATE.exists(), "Clean up the previous fixture first"
    async with AsyncSessionLocal() as db:
        await guard(db)
        user_id = 8_900_000_000_000 + secrets.randbelow(1_000_000)
        assert await db.get(User, user_id) is None
        category_id = await db.scalar(select(Category.id).where(
            Category.is_active.is_(True), Category.parent_id.is_not(None),
        ).order_by(Category.id).limit(1))
        assert category_id is not None
        code = secrets.token_urlsafe(24)
        state = {"user_id": user_id, "service_ids": [], "code": code, "jwt": create_access_token({"sub": str(user_id), "role": "sns_user"}, timedelta(hours=1))}
        # Save cleanup identity before the first commit, including failure paths.
        STATE.write_text(json.dumps(state), encoding="utf-8")
        db.add(User(user_id=user_id, nickname="مالک آزمایشی SNS", first_name="PRIVATE_WEB_TEST_NAME", phone_number="PRIVATE_WEB_TEST_PHONE", is_registered=True))
        await db.flush()
        db.add(UserPrivacySettings(user_id=user_id, is_profile_discoverable=True))
        db.add(SnsLoginToken(user_id=user_id, token_hash=hashlib.sha256(code.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(minutes=20)))
        await db.commit()
        listing = await ServiceService(db).create(ServiceCreateRequest(
            name="کافهٔ آزمایشی هویت", description="خدمات فارسی‌زبان و یک فنجان قهوه در برلین. این مورد برای بررسی محلی است.",
            owner_user_id=user_id, country_code="DE", state="Berlin", city="Berlin",
            persian_language=True, status="published",
            categories=[{"category_id": category_id, "is_primary": True}],
            contacts=[{"title": "وب‌سایت", "type": "url", "value": "https://example.com/sns-local-preview", "is_visible": True},
                      {"title": "تماس خصوصی", "type": "phone", "value": "PRIVATE_WEB_TEST_CONTACT", "is_visible": False}],
        ))
        state["service_ids"].append(listing.id)
        STATE.write_text(json.dumps(state), encoding="utf-8")
        print(json.dumps({"service_id": listing.id, "browser_login_code": code, "state_file": str(STATE)}))


async def check():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    service_id = state["service_ids"][0]
    async with httpx.AsyncClient(base_url=FRONTEND, timeout=60, trust_env=False) as visitor:
        for path in ("/", "/discover?country_code=DE", f"/businesses/{service_id}"):
            response = await visitor.get(path)
            assert response.status_code == 200, (path, response.status_code)
            assert "کافهٔ آزمایشی هویت" in response.text, path
            assert all(private not in response.text for private in ("PRIVATE_WEB_TEST_CONTACT", "PRIVATE_WEB_TEST_NAME", "PRIVATE_WEB_TEST_PHONE"))
        assert (await visitor.get(f"/api/my-businesses/{service_id}")).status_code == 401
        missing = await visitor.get("/businesses/9000000000000000")
        # Next streams dynamic notFound() pages with 200 after headers have
        # flushed; they must still be noindex and contain no business record.
        assert missing.status_code in (200, 404) and 'noindex' in missing.text
        filtered = await visitor.get("/discover?city=NONEXISTENT_LOCAL_TEST_CITY")
        assert filtered.status_code == 200 and "کافهٔ آزمایشی هویت" not in filtered.text
        print("PASS: business home/search/detail/filter/404 and public privacy")

    async with httpx.AsyncClient(base_url=FRONTEND, timeout=60, trust_env=False, cookies={"hoviat_token": state["jwt"]}) as owner:
        response = await owner.get(f"/api/my-businesses/{service_id}")
        assert response.status_code == 200, response.status_code
        business = response.json()["data"]
        assert any(contact["value"] == "PRIVATE_WEB_TEST_CONTACT" for contact in business["contacts"])
        body = {"expected_updated_at": business["updated_at"], "description": "توضیحات تازهٔ آزمایشی"}
        rejected = await owner.patch(f"/api/my-businesses/{service_id}", json=body, headers={"Origin": "https://example.invalid"})
        assert rejected.status_code == 403
        response = await owner.patch(f"/api/my-businesses/{service_id}", json=body, headers={"Origin": FRONTEND})
        assert response.status_code == 200, response.text
        stale = await owner.patch(f"/api/my-businesses/{service_id}", json=body, headers={"Origin": FRONTEND})
        assert stale.status_code == 409, stale.status_code
        assert (await owner.patch(f"/api/my-businesses/{service_id}", json={"status": "archived", "expected_updated_at": response.json()["data"]["updated_at"]}, headers={"Origin": FRONTEND})).status_code == 422
        assert (await owner.get("/api/my-businesses/9000000000000000")).status_code == 404
        # Save through the real backend, then verify the Next private read proxy.
        async with httpx.AsyncClient(base_url="http://127.0.0.1:18743", trust_env=False, headers={"Authorization": "Bearer " + state["jwt"]}) as backend:
            for _ in range(2):
                assert (await backend.post(f"/api/sns/me/service-bookmarks/{service_id}")).status_code == 200
        saved = await owner.get("/api/business-bookmarks")
        assert saved.status_code == 200 and any(item["id"] == service_id for item in saved.json()["data"])
        assert "PRIVATE_WEB_TEST_CONTACT" not in saved.text
        print("PASS: authenticated Next owner edit/409/permissions and private business bookmarks")


async def cleanup():
    if not STATE.exists():
        print("No fixture to clean up")
        return
    state = json.loads(STATE.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as db:
        await guard(db)
        # Only fixture-owned businesses are eligible for deletion.
        await db.execute(delete(Service).where(Service.id.in_(state["service_ids"]), Service.owner_user_id == state["user_id"]))
        await db.execute(delete(JobQueue).where(JobQueue.user_id == state["user_id"]))
        await db.execute(delete(SnsLoginToken).where(SnsLoginToken.user_id == state["user_id"]))
        await db.execute(delete(User).where(User.user_id == state["user_id"], User.nickname == "مالک آزمایشی SNS"))
        await db.commit()
        assert await db.get(User, state["user_id"]) is None
    STATE.unlink()
    print("PASS: synthetic web fixture and related login/queue/bookmark rows removed")


async def main(action):
    try:
        await {"seed": seed, "check": check, "cleanup": cleanup}[action]()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "check", "cleanup"))
    asyncio.run(main(parser.parse_args().action))
