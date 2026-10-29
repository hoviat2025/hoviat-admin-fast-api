"""Exercise live statistics aggregates against an isolated SQLite database."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from app.modules.admin.statistics.repository import AdminStatisticsRepository


class AdminStatisticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.connection.execute(text("""
            CREATE TABLE users_eurobot (
                user_id BIGINT PRIMARY KEY, country TEXT,
                is_in_eurobot BOOLEAN, is_in_hilfen_bot BOOLEAN,
                join_date BIGINT, hilfen_date_join BIGINT
            )
        """))
        self.connection.execute(text("""
            CREATE TABLE services (
                id BIGINT PRIMARY KEY, status TEXT, cover_image_path TEXT
            )
        """))

        async def execute(statement):
            return self.connection.execute(statement)

        self.repository = AdminStatisticsRepository(SimpleNamespace(execute=execute))

    def tearDown(self):
        self.connection.close()
        self.engine.dispose()

    async def test_empty_database_returns_zero_counts(self):
        result = await self.repository.get_statistics()
        self.assertEqual(result.businesses.model_dump(), {
            "total_businesses": 0, "published_businesses": 0, "without_photo": 0,
        })
        self.assertEqual(result.overview.total_users, 0)

    async def test_business_counts_include_all_statuses_and_missing_photos(self):
        self.connection.execute(text("INSERT INTO services VALUES (:id, :status, :cover)"), [
            {"id": 1, "status": "published", "cover": "business-covers/1/photo.jpg"},
            {"id": 2, "status": "published", "cover": None},
            {"id": 3, "status": "draft", "cover": ""},
            {"id": 4, "status": "hidden", "cover": "   "},
            {"id": 5, "status": "archived", "cover": "business-covers/5/photo.jpg"},
        ])
        result = await self.repository.get_statistics()
        self.assertEqual(result.businesses.model_dump(), {
            "total_businesses": 5, "published_businesses": 2, "without_photo": 3,
        })
        self.connection.execute(text("UPDATE services SET cover_image_path = 'new.jpg' WHERE id = 2"))
        refreshed = await self.repository.get_statistics()
        self.assertEqual(refreshed.businesses.without_photo, 2)

    async def test_existing_membership_country_and_join_counts_remain_independent(self):
        recent = int(datetime.now(timezone.utc).timestamp()) - 60
        self.connection.execute(text("""
            INSERT INTO users_eurobot VALUES
                (1, 'ایران', 1, 0, :recent, NULL),
                (2, 'آلمان', 1, 1, :recent, :recent),
                (3, NULL, 0, 0, NULL, NULL),
                (4, 'France', 0, 1, NULL, :recent)
        """), {"recent": recent})
        self.connection.execute(text("INSERT INTO services VALUES (1, 'published', NULL)"))
        result = await self.repository.get_statistics()
        self.assertEqual(result.overview.model_dump(), {
            "total_users": 4, "eurobot_members": 2, "hilfen_members": 2,
            "members_of_both": 1, "members_of_neither": 1,
        })
        self.assertEqual(result.countries.model_dump(), {
            "iran": 1, "germany": 1, "other": 1, "unknown": 1,
        })
        self.assertEqual(result.new_joins.eurobot.last_24_hours, 2)
        self.assertEqual(result.new_joins.hilfen.last_24_hours, 2)
        self.assertEqual(result.businesses.total_businesses, 1)
