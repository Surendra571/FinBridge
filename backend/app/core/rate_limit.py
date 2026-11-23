"""
In-memory and Redis-compatible sliding window rate limiter for security endpoints.
Protects login, registration, and password recovery from brute-force attacks.
"""
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import HTTPException, status
from app.core.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """Sliding-window memory rate limiter for authentication endpoints."""
    def __init__(self):
        # key -> list of request timestamps
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if a key has exceeded max_requests within window_seconds.
        Returns (is_limited, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - window_seconds

        # Prune older entries
        recent = [ts for ts in self._requests[key] if ts > cutoff]
        self._requests[key] = recent

        if len(recent) >= max_requests:
            oldest = recent[0]
            retry_after = int(window_seconds - (now - oldest)) + 1
            return True, max(retry_after, 1)

        self._requests[key].append(now)
        return False, 0

    def check_or_raise(self, key: str, max_requests: int = 5, window_seconds: int = 60) -> None:
        """Evaluate rate limit; raises HTTP 429 Too Many Requests if exceeded."""
        limited, retry_after = self.is_rate_limited(key, max_requests, window_seconds)
        if limited:
            logger.warning("Rate limit exceeded", rate_limit_key=key, retry_after=retry_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )


# Global rate limiter instance
auth_rate_limiter = SlidingWindowRateLimiter()
