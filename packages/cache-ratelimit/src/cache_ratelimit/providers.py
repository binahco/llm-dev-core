"""Providers composables sobre `llm_client.provider.Provider` (ADR-7).

`ThrottledProvider` aplica un token bucket antes de cada llamada;
`CachedProvider` cachea respuestas con TTL. Ambos son composables en tiempo de
ejecución, igual que `ReplayProvider`/LLM de `llm-client` — la hoja no cambia.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterator

from llm_client.provider import Provider, ProviderRequest, ProviderResponse

from .ratelimit import LimiterClock, RateLimiter, RealClock


class ThrottledProvider:
    """Envuelve un Provider y consume un token del bucket por llamada."""

    def __init__(self, inner: Provider, limiter: RateLimiter) -> None:
        self.inner = inner
        self.limiter = limiter
        self.name = f"throttled:{inner.name}"

    def _await(self) -> None:
        self.limiter.acquire()

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self._await()
        return self.inner.complete(request)

    def stream(self, request: ProviderRequest) -> Iterator[str]:
        self._await()
        return self.inner.stream(request)


class CachedProvider:
    """Cache de `complete` con TTL y poda de expirados (los streams no se cachean).

    La clave cubre modelo + mensajes + temperature + max_tokens; el reloj se
    inyecta para tests deterministas.
    """

    def __init__(
        self,
        inner: Provider,
        ttl_seconds: float = 300.0,
        *,
        clock: LimiterClock | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds debe ser > 0, recibido {ttl_seconds!r}")
        self.inner = inner
        self.ttl_seconds = ttl_seconds
        self._clock = clock if clock is not None else RealClock()
        self._store: dict[str, tuple[float, ProviderResponse]] = {}
        self.name = f"cached:{inner.name}"
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(request: ProviderRequest) -> str:
        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _prune(self, now: float) -> None:
        expired = [k for k, (stored_at, _) in self._store.items() if now - stored_at > self.ttl_seconds]
        for key in expired:
            del self._store[key]

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        now = self._clock.monotonic()
        self._prune(now)
        key = self._key(request)
        entry = self._store.get(key)
        if entry is not None:
            stored_at, response = entry
            if now - stored_at <= self.ttl_seconds:
                self.hits += 1
                return response
            del self._store[key]
        self.misses += 1
        response = self.inner.complete(request)
        self._store[key] = (now, response)
        return response

    def stream(self, request: ProviderRequest) -> Iterator[str]:
        self.misses += 1
        return self.inner.stream(request)

    def stats(self) -> dict:
        return {
            "ttl_seconds": self.ttl_seconds,
            "entries": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
        }