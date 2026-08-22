from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sns.profiles.repositories.profile_search import ProfileSearchRepository
from app.modules.sns.profiles.repositories.user_lookup import UserLookupRepository
from app.modules.sns.profiles.services.get_user_profile import GetUserProfileService
from app.modules.sns.profiles.services.search_profiles import SearchProfilesService


def provide_get_user_service(
    db: AsyncSession = Depends(get_db),
) -> GetUserProfileService:
    """
    Dependency injection factory for the 'Get User Profile' feature.
    """
    return GetUserProfileService(UserLookupRepository(db))


def provide_search_profiles_service(
    db: AsyncSession = Depends(get_db),
) -> SearchProfilesService:
    """
    Dependency injection factory for the 'Search User Profiles' feature.
    """
    return SearchProfilesService(ProfileSearchRepository(db))
