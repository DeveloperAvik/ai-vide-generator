import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings

_hits: dict[str, deque] = defaultdict(deque)


async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "?"
    limit = get_settings().rate_limit_per_minute
    # login is much stricter to slow brute force
    if request.url.path.endswith("/auth/login"):
        limit = 10
    key = f"{ip}:{request.url.path.endswith('/auth/login')}"
    q, t = _hits[key], time.monotonic()
    while q and t - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    q.append(t)
    return await call_next(request)
