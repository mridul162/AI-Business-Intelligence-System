from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class InMemoryRateLimiter:
    """Thread-safe token bucket for a single application instance."""

    def __init__(
        self,
        *,
        requests: int = 30,
        window_seconds: int = 60,
        burst: int = 10,
        clock=time.monotonic,
    ) -> None:
        if requests <= 0 or window_seconds <= 0 or burst < 0:
            raise ValueError("Rate-limit values are outside their valid range.")
        self.requests = requests
        self.window_seconds = window_seconds
        self.capacity = max(1, burst)
        self.refill_rate = requests / window_seconds
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, client_id: str) -> tuple[bool, int]:
        """Consume one token and return ``(allowed, retry_after_seconds)``."""
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(client_id)
            if bucket is None:
                bucket = _Bucket(float(self.capacity), now)
                self._buckets[client_id] = bucket

            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(
                float(self.capacity), bucket.tokens + elapsed * self.refill_rate
            )
            bucket.updated_at = now

            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, 0

            retry_after = max(1, int((1 - bucket.tokens) / self.refill_rate + 0.999))
            return False, retry_after


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply an in-process client-IP quota to HTTP requests.

    This store is suitable for one application instance only. A distributed
    deployment needs a shared store such as Redis.
    """

    def __init__(
        self,
        app,
        *,
        limiter: InMemoryRateLimiter | None = None,
        requests: int = 30,
        window_seconds: int = 60,
        burst: int = 10,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter(
            requests=requests,
            window_seconds=window_seconds,
            burst=burst,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        client_id = request.client.host if request.client else "unknown"
        allowed, retry_after = self.limiter.allow(client_id)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests.",
                        "stage": "rate_limiting",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)