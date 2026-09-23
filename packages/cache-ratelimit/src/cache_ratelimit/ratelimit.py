"""Relojes y token bucket (ADR-7). El reloj se inyecta para que los tests sean
deterministas (D4): en CI el `FakeClock` de los tests nunca bloquea de verdad."""

from __future__ import annotations

import time
from typing import Protocol


class LimiterClock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class RealClock:
    """Reloj del sistema: `time.monotonic` + `time.sleep`."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class RateLimiter:
    """Token bucket de una sola operación por usuario.

    Repone `rpm` tokens por minuto hasta un tope `burst` (>= 1). Cada `acquire()`
    consume un token; si el bucket está vacío, duerme (o avanza el reloj inyectado)
    hasta recuperar uno. Expone contadores para la UI del consumidor.
    """

    def __init__(
        self,
        rpm: float,
        burst: int | None = None,
        *,
        clock: LimiterClock | None = None,
    ) -> None:
        if rpm <= 0:
            raise ValueError(f"rpm debe ser > 0, recibido {rpm!r}")
        if burst is not None and burst < 1:
            raise ValueError(f"burst debe ser >= 1, recibido {burst!r}")
        self._clock = clock if clock is not None else RealClock()
        self._rate = rpm / 60.0
        self._capacity = float(burst if burst is not None else max(1, int(rpm)))
        self._tokens = self._capacity
        self._last = self._clock.monotonic()
        self._total_wait = 0.0
        self.calls = 0
        self.blocked_calls = 0

    def _refill(self) -> None:
        now = self._clock.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)

    def acquire(self) -> None:
        self._refill()
        self.calls += 1
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return
        need = 1.0 - self._tokens
        wait = need / self._rate
        self._clock.sleep(wait)
        self._total_wait += wait
        self.blocked_calls += 1
        self._refill()
        self._tokens = max(0.0, self._tokens - 1.0)

    @property
    def tokens(self) -> float:
        self._refill()
        return self._tokens

    @property
    def wait_seconds(self) -> float:
        return self._total_wait

    def stats(self) -> dict:
        return {
            "rpm": round(self._rate * 60.0, 3),
            "burst": self._capacity,
            "tokens": round(self.tokens, 4),
            "calls": self.calls,
            "blocked_calls": self.blocked_calls,
            "total_wait_seconds": round(self._total_wait, 4),
        }