from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from app.models.user import User
from app.models.user_privacy_settings import PrivacyScope, UserPrivacySettings
from app.modules.sns.profiles.schemas.profile_requests import ProfileSearchParams


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
        if params.q:
            sq = f"%{params.q}%"
            conditions.append(
                or_(
                    and_(
                        User.username.ilike(sq),
                        UserPrivacySettings.username_visibility == PrivacyScope.public,
                    ),
                    and_(
                        User.nickname.ilike(sq),
                        UserPrivacySettings.nickname_visibility == PrivacyScope.public,
                    ),
                    and_(
                        User.first_name.ilike(sq),
                        UserPrivacySettings.first_name_visibility == PrivacyScope.public,
                    ),
                    and_(
                        User.last_name.ilike(sq),
                        UserPrivacySettings.last_name_visibility == PrivacyScope.public,
                    ),
                    and_(
                        User.bio.ilike(sq),
                        UserPrivacySettings.bio_visibility == PrivacyScope.public,
                    ),
                    and_(
                        User.occupation.ilike(sq),
                        UserPrivacySettings.occupation_visibility == PrivacyScope.public,
                    ),
                )
            )

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
