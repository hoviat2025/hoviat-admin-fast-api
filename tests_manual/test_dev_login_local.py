"""Exercise local synthetic login on PostgreSQL, rolling back all fixture writes."""

import asyncio
from ipaddress import ip_address

from jose import jwt
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.modules.sns.auth.services.dev_login import DevLoginService, dev_token_secret


async def main():
    url = make_url(settings.DATABASE_URL)
    assert (url.host, url.port, url.database) == ("127.0.0.1", 5433, "hoviat_service_dev")
    assert settings.DISABLE_BACKGROUND_WORKERS and settings.DEV_LOGIN_ENABLED
    assert settings.DEV_LOGIN_USER_ID < 0
    engine = create_async_engine(settings.DATABASE_URL, connect_args={"timeout": 5})
    params = {"id": settings.DEV_LOGIN_USER_ID}
    identity_sql = text("SELECT user_id, mode, nickname FROM users_eurobot WHERE user_id=:id")
    privacy_sql = text("SELECT count(*) FROM user_privacy_settings WHERE user_id=:id")
    queue_sql = text("SELECT count(*) FROM job_queue")
    try:
        async with engine.connect() as connection:
            identity = (await connection.execute(text("SELECT current_database(), inet_server_addr()::text"))).one()
            assert identity[0] == "hoviat_service_dev"
            assert ip_address(identity[1].split("/", 1)[0]).is_loopback
            print("GUARD PASS: local hoviat_service_dev with workers disabled")
            before_user = (await connection.execute(identity_sql, params)).first()
            before_privacy = await connection.scalar(privacy_sql, params)
            before_queue = await connection.scalar(queue_sql)
            await connection.rollback()
            outer = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                    service = DevLoginService(db)
                    first = await service.execute()
                    second = await service.execute()
                    assert first.user_id == second.user_id == settings.DEV_LOGIN_USER_ID
                    for session in (first, second):
                        claims = jwt.decode(session.access_token, dev_token_secret(), algorithms=[settings.ALGORITHM])
                        assert claims["dev_login"] is True
                        assert claims["sub"] == str(settings.DEV_LOGIN_USER_ID)
                        assert claims["role"] == "sns_user"
                    assert await db.scalar(privacy_sql, params) == 1
                    assert await db.scalar(queue_sql) == before_queue
                    print("PASS: two logins reuse one synthetic identity and issue SNS JWTs")
                    print("PASS: privacy row exists and job queue is unchanged")
            finally:
                await outer.rollback()
        async with engine.connect() as connection:
            assert (await connection.execute(identity_sql, params)).first() == before_user
            assert await connection.scalar(privacy_sql, params) == before_privacy
            assert await connection.scalar(queue_sql) == before_queue
        print("PASS: rollback preserved original dev identity/privacy and job queue")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
