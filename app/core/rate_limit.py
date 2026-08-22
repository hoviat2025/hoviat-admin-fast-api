import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    """
    Simple in-memory fixed-window rate limiter.

    Suitable for a single-process deployment. Timestamps are pruned on every
    check, so memory stays bounded even under sustained load. Each process (or
    container replica) enforces the limit independently.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        bucket = self._hits[key]

        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            return False

        bucket.append(now)
        return True


def get_client_ip(request: Request) -> str:
    """
    Resolve the caller's IP address.

    Behind the Cloudflare Worker proxy, the real client IP arrives in the
    X-Real-IP header. Fall back to the direct socket address for requests that
    do not pass through the proxy.
    """
    forwarded = request.headers.get("X-Real-IP")
    if forwarded:
        return forwarded.strip()

    if request.client:
        return request.client.host

    return "unknown"


def make_rate_limit_dependency(limiter: RateLimiter):
    """
    Build a FastAPI dependency that rejects requests once the limiter trips.
    """

    async def rate_limit(request: Request) -> None:
        if not limiter.is_allowed(get_client_ip(request)):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
            )

    return rate_limit
