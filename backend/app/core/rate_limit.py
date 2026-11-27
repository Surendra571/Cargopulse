import time
from collections import defaultdict
from typing import Dict, List
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Sliding-window rate limiter for sensitive endpoints (login, password reset)."""

    def __init__(self, requests_limit: int, window_seconds: int):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.history: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.time()
        window_start = now - self.window_seconds

        # Prune older entries
        self.history[key] = [t for t in self.history[key] if t > window_start]

        if len(self.history[key]) >= self.requests_limit:
            retry_after = int(self.window_seconds - (now - self.history[key][0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Please try again in {max(retry_after, 1)} seconds.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self.history[key].append(now)


# 10 login attempts per 60 seconds per IP
login_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)

# 5 password reset requests per 300 seconds per IP
password_reset_rate_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=300)


def rate_limit_login(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    login_rate_limiter.check(f"login:{client_ip}")


def rate_limit_password_reset(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    password_reset_rate_limiter.check(f"reset:{client_ip}")
