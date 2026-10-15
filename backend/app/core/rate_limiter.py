import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter per client IP or authorization identity."""

    def __init__(self, default_limit: int = 120, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        # {client_key: [timestamp, timestamp, ...]}
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(
        self,
        client_key: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> Tuple[bool, int, float]:
        """Check if client request is within the sliding window quota.

        Returns:
            Tuple[bool, int, float]: (is_allowed, remaining_requests, reset_after_seconds)
        """
        now = time.time()
        max_req = limit or self.default_limit
        win_sec = window or self.window_seconds
        cutoff = now - win_sec

        # Prune timestamps older than window
        timestamps = [ts for ts in self._requests[client_key] if ts > cutoff]
        self._requests[client_key] = timestamps

        current_count = len(timestamps)
        if current_count >= max_req:
            oldest_ts = timestamps[0]
            retry_after = max(1.0, round(oldest_ts + win_sec - now, 1))
            return False, 0, retry_after

        # Record this request
        timestamps.append(now)
        self._requests[client_key] = timestamps
        remaining = max_req - len(timestamps)
        return True, remaining, float(win_sec)

    def check_rate_limit(
        self,
        client_key: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> None:
        """Enforce rate limit, raising HTTP 429 Too Many Requests if quota is exceeded."""
        allowed, remaining, retry_after = self.is_allowed(client_key, limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please retry after some time.",
                headers={"Retry-After": str(int(retry_after))},
            )

    def reset(self, client_key: Optional[str] = None) -> None:
        """Reset rate limit history for a specific client or all clients."""
        if client_key:
            self._requests.pop(client_key, None)
        else:
            self._requests.clear()


# Global Rate Limiter Singleton
rate_limiter = SlidingWindowRateLimiter()
