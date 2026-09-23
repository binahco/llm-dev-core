"""Tests de bot-base: reloj falso, horario, idempotencia y digest (D4)."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import pytest

from bot_base import JsonRunStore, RunStore, Schedule, Task, run_tasks
from bot_base.digest import Digest, TaskResult


class FakeClock:
    def __init__(self, tick: float = 0.0, wall: datetime | None = None) -> None:
        self.tick = tick
        self.wall = wall or datetime(2026, 9, 30, 9, 0, 0)

    def monotonic(self) -> float:
        return self.tick

    def sleep(self, seconds: float) -> None:
        self.tick += seconds

    def now(self) -> datetime:
        return self.wall


class InMemoryStore(RunStore):
    def __init__(self) -> None:
        self.state: dict[str, float] = {}

    def last_run(self, task_id: str) -> float | None:
        return self.state.get(task_id)

    def mark_done(self, task_id: str, at_monotonic: float) -> None:
        self.state[task_id] = at_monotonic


def counting(registry: dict[str, int]) -> Callable[[], str]:
    def _run() -> str:
        registry["count"] = registry.get("count", 0) + 1
        return "ok línea"
    return _run


class TestSchedule:
    def test_primera_corrida_es_debida(self) -> None:
        assert Schedule(every_seconds=10.0).is_due(0.0, None, datetime.now())

    def test_intervalo_no_cumplido_es_skipped(self) -> None:
        clock = FakeClock(tick=5.0)
        schedule = Schedule(every_seconds=10.0)
        assert schedule.is_due(clock.monotonic(), 0.0, clock.now()) is False

    def test_intervalo_cumplido_es_debido(self) -> None:
        clock = FakeClock(tick=11.0)
        schedule = Schedule(every_seconds=10.0)
        assert schedule.is_due(clock.monotonic(), 0.0, clock.now()) is True

    def test_predicado_de_calendario(self) -> None:
        schedule = Schedule(when=lambda now: now.weekday() == 0)
        assert schedule.is_due(0.0, 0.0, datetime(2026, 9, 28)) is True  # lunes
        assert schedule.is_due(0.0, 0.0, datetime(2026, 9, 30)) is False  # miércoles

    def test_schedule_invalido(self) -> None:
        with pytest.raises(ValueError, match="Schedule"):
            Schedule()
        with pytest.raises(ValueError, match="every_seconds"):
            Schedule(every_seconds=0)


class TestRunTasks:
    def test_corrige_tareas_y_marca_done(self) -> None:
        clock = FakeClock()
        store = InMemoryStore()
        registry: dict[str, int] = {}
        digest = run_tasks(
            [Task("t1", Schedule(every_seconds=10.0), run=counting(registry))],
            store=store,
            clock=clock,
        )
        assert [r.task_id for r in digest.ok] == ["t1"]
        assert [r.task_id for r in digest.failed] == []
        assert store.state == {"t1": 0.0}

    def test_idempotencia_con_store(self) -> None:
        clock = FakeClock()
        store = InMemoryStore()
        registry: dict[str, int] = {}
        task = Task("t1", Schedule(every_seconds=10.0), run=counting(registry))
        first = run_tasks([task], store=store, clock=clock)
        second = run_tasks([task], store=store, clock=clock)
        assert first.results[0].status == "ok"
        assert second.results[0].status == "skipped"
        assert registry["count"] == 1

    def test_intervalo_no_cumplido_no_vuelve_a_correr(self) -> None:
        clock = FakeClock(tick=5.0)
        store = InMemoryStore()
        store.mark_done("t1", 0.0)
        registry: dict[str, int] = {}
        digest = run_tasks(
            [Task("t1", Schedule(every_seconds=10.0), run=counting(registry))],
            store=store,
            clock=clock,
        )
        assert digest.results[0].status == "skipped"
        assert registry.get("count", 0) == 0

    def test_tarea_que_falla_no_marca_done(self) -> None:
        clock = FakeClock()
        store = InMemoryStore()

        def boom() -> str:
            raise RuntimeError("proveedor caído")

        task = Task("t1", Schedule(every_seconds=10.0), run=boom)
        digest = run_tasks([task], store=store, clock=clock)
        assert [r.task_id for r in digest.failed] == ["t1"]
        assert "RuntimeError: proveedor caído" in digest.results[0].detail
        assert store.state == {}

    def test_digest_text_resume(self) -> None:
        digest = Digest(
            results=[
                TaskResult(task_id="a", status="ok", detail="x"),
                TaskResult(task_id="b", status="skipped"),
            ]
        )
        text = digest.text()
        assert "1 ok · 1 skipped · 0 failed" in text


class TestJsonRunStore:
    def test_persiste_y_recarga(self, tmp_path) -> None:
        store = JsonRunStore(tmp_path / "state.json")
        store.mark_done("t1", 12.345)
        reloaded = JsonRunStore(tmp_path / "state.json")
        assert reloaded.last_run("t1") == pytest.approx(12.345)
        assert reloaded.last_run("t2") is None

    def test_escritura_atomica_crea_archivo(self, tmp_path) -> None:
        path = tmp_path / "sub" / "state.json"
        JsonRunStore(path).mark_done("t1", 1.0)
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("{")