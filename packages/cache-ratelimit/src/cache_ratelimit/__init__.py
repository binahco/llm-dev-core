"""cache-ratelimit: token bucket con reloj inyectable y caché con TTL (ADR-7).

Composición (la hoja `llm-client` no cambia):

    from cache_ratelimit import RateLimiter, ThrottledProvider, CachedProvider
    provider = ThrottledProvider(
        CachedProvider(inner, ttl_seconds=600.0, clock=my_clock),
        RateLimiter(rpm=60, burst=12, clock=my_clock),
    )
    client = LlmClient(provider, ...)
"""

from .providers import CachedProvider, ThrottledProvider
from .ratelimit import LimiterClock, RateLimiter, RealClock

__all__ = [
    "CachedProvider",
    "LimiterClock",
    "RateLimiter",
    "RealClock",
    "ThrottledProvider",
]
