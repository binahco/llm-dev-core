"""Reloj de auth-base (ADR-13). Inyectado para que el vencimiento de una clave sea
determinista en tests y CI (D4), igual que `LimiterClock` de cache-ratelimit.

`now()` es la hora de pared en segundos Unix: sirve para "esta clave vence el…".
"""

from __future__ import annotations

import time
from typing import Protocol


class AuthClock(Protocol):
    def now(self) -> float: ...


class RealClock:
    def now(self) -> float:
        return time.time()
