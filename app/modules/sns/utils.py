from typing import Optional

from app.core.config import settings


def resolve_sync_source(user) -> str:
    """
    Determine the queue 'source' for a user's channel sync, mirroring the
    logic used by UserManagementService and CronSyncService.

    The source is derived strictly from the bot-presence flags, which are
    set only by bot upserts. A user with no membership reported yet resolves
    to "none": the queue still syncs their main-channel entry, but sends no
    public/hilfen announcements, and the source upgrades automatically when a
    bot upsert arrives (see merge_job_sources).
    """
    if user.is_in_eurobot and user.is_in_hilfen_bot:
        return "both"
    if user.is_in_hilfen_bot:
        return "hilfenbot"
    if user.is_in_eurobot:
        return "eurobot"
    return "none"


def assemble_profile_url(profile_path: Optional[str]) -> Optional[str]:
    """
    Turn a stored profile picture path into an absolute URL.
    Returns the raw value unchanged when it is already absolute or when no
    media base URL is configured.
    """
    if not profile_path:
        return None

    if profile_path.startswith("http://") or profile_path.startswith("https://"):
        return profile_path

    base = (settings.PROFILE_MEDIA_URL or "").rstrip("/")
    if not base:
        return profile_path

    return f"{base}/{profile_path.lstrip('/')}"
