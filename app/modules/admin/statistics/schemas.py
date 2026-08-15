from pydantic import BaseModel, Field


class StatisticsOverview(BaseModel):
    total_users: int = Field(..., description="Unique rows in the unified users table")
    eurobot_members: int
    hilfen_members: int
    members_of_both: int
    members_of_neither: int


class JoinPeriodCounts(BaseModel):
    last_24_hours: int
    last_7_days: int
    last_30_days: int
    last_365_days: int


class NewJoinStatistics(BaseModel):
    eurobot: JoinPeriodCounts
    hilfen: JoinPeriodCounts


class CountryStatistics(BaseModel):
    iran: int
    germany: int
    other: int
    unknown: int


class AdminStatisticsResponse(BaseModel):
    overview: StatisticsOverview
    new_joins: NewJoinStatistics
    countries: CountryStatistics
