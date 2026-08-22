from app.core.rate_limit import RateLimiter, make_rate_limit_dependency

# Limits apply to the public SNS endpoints only (not the bot webhooks or cron).
# Values are deliberately conservative for a small user base and easy to tune.
login_limiter = RateLimiter(limit=10, window_seconds=60)
search_limiter = RateLimiter(limit=60, window_seconds=60)
profile_view_limiter = RateLimiter(limit=60, window_seconds=60)

login_rate_limit = make_rate_limit_dependency(login_limiter)
search_rate_limit = make_rate_limit_dependency(search_limiter)
profile_view_rate_limit = make_rate_limit_dependency(profile_view_limiter)
