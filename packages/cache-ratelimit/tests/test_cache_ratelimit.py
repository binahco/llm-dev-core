"""Tests de cache-ratelimit: reloj falso, deterministas (D4)."""

from __future__ import annotations

from typing import Iterator

import pytest

from cache_ratelimit import CachedProvider, RateLimiter, ThrottledProvider
from llm_client.provider import ProviderRequest, ProviderResponse


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.slept += seconds


class StubProvider:
    def __init__(self, text: str = "ok") -> None:
        self.name = "stub"
        self.text = text
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(text=f"{self.text}-{self.calls}", model=request.model)

    def stream(self, request: ProviderRequest) -> Iterator[str]:
        self.calls += 1
        yield self.text


def make_request(model: str = "stub-1") -> ProviderRequest:
    return ProviderRequest(model=model, messages=[{"role": "user", "content": "hola"}])


class TestRateLimiter:
    def test_ráfaga_de_burst_pasa_sin_esperar(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(rpm=60, burst=5, clock=clock)
        for _ in range(5):
            limiter.acquire()
        assert clock.slept == 0.0
        assert limiter.blocked_calls == 0

    def test_seisima_llamada_espera_un_token(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(rpm=60, burst=5, clock=clock)
        for _ in range(6):
            limiter.acquire()
        assert clock.slept == pytest.approx(1.0)
        assert limiter.blocked_calls == 1

    def test_rpm_define_el_ritmo(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(rpm=30, burst=1, clock=clock)
        limiter.acquire()
        limiter.acquire()
        assert clock.slept == pytest.approx(2.0)

    def test_rpm_invalido_y_burst_invalido(self) -> None:
        with pytest.raises(ValueError, match="rpm"):
            RateLimiter(rpm=0)
        with pytest.raises(ValueError, match="burst"):
            RateLimiter(rpm=60, burst=0)

    def test_stats_reflejan_estado(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(rpm=60, burst=2, clock=clock)
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()
        stats = limiter.stats()
        assert stats["calls"] == 3
        assert stats["blocked_calls"] == 1
        assert stats["rpm"] == pytest.approx(60.0)


class TestThrottledProvider:
    def test_espera_el_bucket_antes_de_llamar_al_inner(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        limiter = RateLimiter(rpm=60, burst=1, clock=clock)
        provider = ThrottledProvider(inner, limiter)
        provider.complete(make_request())
        provider.complete(make_request())
        assert inner.calls == 2
        assert clock.slept == pytest.approx(1.0)

    def test_stream_también_consume_token(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        limiter = RateLimiter(rpm=60, burst=1, clock=clock)
        provider = ThrottledProvider(inner, limiter)
        assert list(provider.stream(make_request())) == ["ok"]
        assert list(provider.stream(make_request())) == ["ok"]
        assert clock.slept == pytest.approx(1.0)


class TestCachedProvider:
    def test_hit_y_miss_con_una_sola_llamada_al_inner(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        provider = CachedProvider(inner, ttl_seconds=60.0, clock=clock)
        first = provider.complete(make_request())
        second = provider.complete(make_request())
        assert inner.calls == 1
        assert first == second
        assert provider.hits == 1
        assert provider.misses == 1

    def test_ttl_expira_y_fuerza_una_nueva_llamada(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        provider = CachedProvider(inner, ttl_seconds=10.0, clock=clock)
        provider.complete(make_request())
        clock.now = 11.0
        provider.complete(make_request())
        assert inner.calls == 2
        assert provider.hits == 0

    def test_poda_de_expirados_reduce_el_almacen(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        provider = CachedProvider(inner, ttl_seconds=10.0, clock=clock)
        provider.complete(make_request("model-a"))
        provider.complete(make_request("model-b"))
        assert len(provider._store) == 2
        clock.now = 11.0
        provider.complete(make_request("model-c"))
        assert len(provider._store) == 1

    def test_llaves_distintas_por_modelo(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        provider = CachedProvider(inner, ttl_seconds=60.0, clock=clock)
        provider.complete(make_request("model-a"))
        provider.complete(make_request("model-b"))
        assert inner.calls == 2
        assert provider.misses == 2

    def test_streams_no_se_cachean(self) -> None:
        clock = FakeClock()
        inner = StubProvider()
        provider = CachedProvider(inner, ttl_seconds=60.0, clock=clock)
        list(provider.stream(make_request()))
        list(provider.stream(make_request()))
        assert inner.calls == 2

    def test_ttl_invalido(self) -> None:
        with pytest.raises(ValueError, match="ttl"):
            CachedProvider(StubProvider(), ttl_seconds=0)