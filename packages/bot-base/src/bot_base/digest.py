"""Digest del bot (ADR-8): el resultado de una corrida, lista para consumir
(texto plano para el resumen LLM del consumidor o JSON para el estado).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

STATUS = ("ok", "skipped", "failed")


class TaskResult(BaseModel):
    task_id: str
    status: str = Field(pattern="^(ok|skipped|failed)$")
    detail: str = ""


class Digest(BaseModel):
    results: list[TaskResult] = Field(default_factory=list)

    @property
    def ok(self) -> list[TaskResult]:
        return [r for r in self.results if r.status == "ok"]

    @property
    def skipped(self) -> list[TaskResult]:
        return [r for r in self.results if r.status == "skipped"]

    @property
    def failed(self) -> list[TaskResult]:
        return [r for r in self.results if r.status == "failed"]

    def text(self) -> str:
        lines = [
            f"- {r.task_id}: {r.status}" + (f" — {r.detail}" if r.detail else "")
            for r in self.results
        ]
        summary = f"{len(self.ok)} ok · {len(self.skipped)} skipped · {len(self.failed)} failed"
        return summary + "\n" + "\n".join(lines)