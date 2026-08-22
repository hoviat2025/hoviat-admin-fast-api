from fastapi import Depends, Request

from app.core.rate_limit import RateLimiter, get_client_ip, make_rate_limit_dependency
from app.models.user import User
from app.modules.sns.dependencies import get_current_sns_user

# Limits apply to the public SNS endpoints only (not the bot webhooks or cron).
# Values are deliberately conservative for a small user base and easy to tune.
login_limiter = RateLimiter(limit=10, window_seconds=60)
search_limiter = RateLimiter(limit=60, window_seconds=60)
profile_view_limiter = RateLimiter(limit=60, window_seconds=60)
profile_picture_user_limiter = RateLimiter(limit=10, window_seconds=60 * 60)
profile_picture_ip_limiter = RateLimiter(limit=20, window_seconds=60 * 60)

login_rate_limit = make_rate_limit_dependency(login_limiter)
search_rate_limit = make_rate_limit_dependency(search_limiter)
profile_view_rate_limit = make_rate_limit_dependency(profile_view_limiter)


async def profile_picture_rate_limit(
    request: Request,
    user: User = Depends(get_current_sns_user),
) -> None:
    """Apply upload limits after authentication resolves the user identity."""
    client_ip = get_client_ip(request)
    if not profile_picture_ip_limiter.is_allowed(client_ip):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Profile picture upload limit exceeded. Please try again later.",
        )

    if not profile_picture_user_limiter.is_allowed(str(user.user_id)):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Profile picture upload limit exceeded. Please try again later.",
        )
