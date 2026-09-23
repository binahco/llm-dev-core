"""Reloj del bot (ADR-8). Inyectado para que los tests y el CI sean
deterministas (D4), igual que `LimiterClock` de cache-ratelimit.

`now()` es la hora de pared (calendario), para decisiones del tipo "corre el
lunes"; `monotonic()` es el tiempo físico para intervalos. Un `FakeBotClock`
las avanza a mano en los tests.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Protocol


class BotClock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    def now(self) -> datetime: ...


class RealClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> datetime:
        return datetime.now()