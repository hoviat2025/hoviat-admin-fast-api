from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.admin.statistics.schemas import (
    AdminStatisticsResponse,
    CountryStatistics,
    JoinPeriodCounts,
    NewJoinStatistics,
    StatisticsOverview,
)


class AdminStatisticsRepository:
    """Database calculations for the admin statistics page.

    Eurobot and Hilfen joining counts intentionally use their own timestamp
    columns. A user who joined both services can therefore appear once in
    each service's joining statistics, while the overview remains unique-user
    based.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_statistics(self) -> AdminStatisticsResponse:
        now = int(datetime.now(timezone.utc).timestamp())
        cutoffs = {
            "last_24_hours": now - 24 * 60 * 60,
            "last_7_days": now - 7 * 24 * 60 * 60,
            "last_30_days": now - 30 * 24 * 60 * 60,
            "last_365_days": now - 365 * 24 * 60 * 60,
        }

        country = func.trim(User.country)
        known_country = User.country.is_not(None) & (country != "")

        def count_if(condition):
            return func.count(User.user_id).filter(condition)

        statement = select(
            func.count(User.user_id).label("total_users"),
            count_if(User.is_in_eurobot.is_(True)).label("eurobot_members"),
            count_if(User.is_in_hilfen_bot.is_(True)).label("hilfen_members"),
            count_if(
                User.is_in_eurobot.is_(True) & User.is_in_hilfen_bot.is_(True)
            ).label("members_of_both"),
            count_if(
                User.is_in_eurobot.is_(False) & User.is_in_hilfen_bot.is_(False)
            ).label("members_of_neither"),
            *[
                count_if(
                    (User.join_date.is_not(None))
                    & (User.join_date >= cutoff)
                    & (User.join_date <= now)
                ).label(f"eurobot_{name}")
                for name, cutoff in cutoffs.items()
            ],
            *[
                count_if(
                    (User.hilfen_date_join.is_not(None))
                    & (User.hilfen_date_join >= cutoff)
                    & (User.hilfen_date_join <= now)
                ).label(f"hilfen_{name}")
                for name, cutoff in cutoffs.items()
            ],
            count_if(country == "ایران").label("iran"),
            count_if(country == "آلمان").label("germany"),
            count_if(~known_country | (country == "")).label("unknown"),
            count_if(
                known_country & (country != "ایران") & (country != "آلمان")
            ).label("other"),
        )

        row = (await self.db.execute(statement)).one()
        values = row._mapping

        def periods(prefix: str) -> JoinPeriodCounts:
            return JoinPeriodCounts(
                last_24_hours=values[f"{prefix}_last_24_hours"] or 0,
                last_7_days=values[f"{prefix}_last_7_days"] or 0,
                last_30_days=values[f"{prefix}_last_30_days"] or 0,
                last_365_days=values[f"{prefix}_last_365_days"] or 0,
            )

        return AdminStatisticsResponse(
            overview=StatisticsOverview(
                total_users=values["total_users"] or 0,
                eurobot_members=values["eurobot_members"] or 0,
                hilfen_members=values["hilfen_members"] or 0,
                members_of_both=values["members_of_both"] or 0,
                members_of_neither=values["members_of_neither"] or 0,
            ),
            new_joins=NewJoinStatistics(
                eurobot=periods("eurobot"),
                hilfen=periods("hilfen"),
            ),
            countries=CountryStatistics(
                iran=values["iran"] or 0,
                germany=values["germany"] or 0,
                other=values["other"] or 0,
                unknown=values["unknown"] or 0,
            ),
        )
