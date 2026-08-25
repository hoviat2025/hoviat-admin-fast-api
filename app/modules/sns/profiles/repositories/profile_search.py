from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from app.models.user import User
from app.models.user_privacy_settings import PrivacyScope, UserPrivacySettings
from app.modules.sns.profiles.schemas.profile_requests import ProfileSearchParams

# Fields searched by the global "q" query, paired with their privacy column.
_GLOBAL_SEARCH_FIELDS = (
    (User.username, UserPrivacySettings.username_visibility),
    (User.nickname, UserPrivacySettings.nickname_visibility),
    (User.first_name, UserPrivacySettings.first_name_visibility),
    (User.last_name, UserPrivacySettings.last_name_visibility),
    (User.bio, UserPrivacySettings.bio_visibility),
    (User.occupation, UserPrivacySettings.occupation_visibility),
    (User.country, UserPrivacySettings.country_visibility),
)

# Upper bound on words considered in a global search; extras are ignored.
GLOBAL_SEARCH_MAX_WORDS = 5


def _build_global_search_conditions(q: str) -> list:
    """One OR-over-public-fields block per word, ANDed across words."""
    words = q.split()[:GLOBAL_SEARCH_MAX_WORDS]

    word_conditions = []
    for word in words:
        pattern = f"%{word}%"
        word_conditions.append(
            or_(
                *[
                    and_(column.ilike(pattern), visibility == PrivacyScope.public)
                    for column, visibility in _GLOBAL_SEARCH_FIELDS
                ]
            )
        )

    if not word_conditions:
        return []

    return [and_(*word_conditions)]


class ProfileSearchRepository:
    """
    Handles dynamic, privacy-aware database queries for searching users.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_profiles(self, params: ProfileSearchParams):
        # 1. Base Query: JOIN the privacy settings.
        # contains_eager maps the joined table to User.privacy_settings so we
        # don't trigger N+1 queries in the Service layer. social_links is loaded
        # eagerly because the response may expose it.
        stmt = (
            select(User)
            .join(UserPrivacySettings, User.user_id == UserPrivacySettings.user_id)
            .options(
                contains_eager(User.privacy_settings),
                selectinload(User.social_links),
            )
        )

        conditions = []

        # 2. Global Requirement: Profile must be discoverable.
        conditions.append(UserPrivacySettings.is_profile_discoverable == True)

        # 3. Standard exact matches (No privacy checks required).
        if params.is_ban is not None:
            conditions.append(User.is_ban == params.is_ban)
        if params.is_registered is not None:
            conditions.append(User.is_registered == params.is_registered)

        # 4. Privacy-Aware Partial Matches (ILIKE).
        if params.username:
            conditions.append(
                and_(
                    User.username.ilike(f"%{params.username}%"),
                    UserPrivacySettings.username_visibility == PrivacyScope.public,
                )
            )

        if params.nickname:
            conditions.append(
                and_(
                    User.nickname.ilike(f"%{params.nickname}%"),
                    UserPrivacySettings.nickname_visibility == PrivacyScope.public,
                )
            )

        if params.first_name:
            conditions.append(
                and_(
                    User.first_name.ilike(f"%{params.first_name}%"),
                    UserPrivacySettings.first_name_visibility == PrivacyScope.public,
                )
            )

        if params.last_name:
            conditions.append(
                and_(
                    User.last_name.ilike(f"%{params.last_name}%"),
                    UserPrivacySettings.last_name_visibility == PrivacyScope.public,
                )
            )

        if params.bio:
            conditions.append(
                and_(
                    User.bio.ilike(f"%{params.bio}%"),
                    UserPrivacySettings.bio_visibility == PrivacyScope.public,
                )
            )

        if params.occupation:
            conditions.append(
                and_(
                    User.occupation.ilike(f"%{params.occupation}%"),
                    UserPrivacySettings.occupation_visibility == PrivacyScope.public,
                )
            )

        # 5. Privacy-Aware Exact Match.
        if params.country:
            conditions.append(
                and_(
                    User.country == params.country,
                    UserPrivacySettings.country_visibility == PrivacyScope.public,
                )
            )

        # 6. Global Search "q" (Any matching field MUST be public).
        # Multi-word queries are AND-of-ORs: every word must appear somewhere
        # in a public field (country included). Capped at 5 words.
        if params.q:
            conditions.extend(_build_global_search_conditions(params.q))

        # 7. Apply conditions dynamically.
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Apply stable sorting.
        stmt = stmt.order_by(User.user_id.desc())

        # 8. Get total count for pagination metadata.
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)

        # Get paginated data.
        paginated_stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        result = await self.db.execute(paginated_stmt)
        users = result.scalars().all()

        return users, total
