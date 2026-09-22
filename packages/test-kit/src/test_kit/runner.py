from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from llm_client import CompletionResult, ValidationResult
from pydantic import BaseModel, Field

from .criteria import CriterionResult, deterministic_match, json_match, schema_match
from .dataset import EvalCase, EvalDataset

Judge = Callable[[EvalCase], CompletionResult]


class CaseResult(BaseModel):
    index: int
    passed: bool
    detail: str = ""


class EvalReport(BaseModel):
    prompt_id: str
    prompt_version: str
    mode: str
    threshold: float
    total: int
    passed: int
    pass_rate: float
    threshold_ok: bool
    cost_usd: Decimal = Field(default_factory=Decimal)
    cases: list[CaseResult] = Field(default_factory=list)


def _apply(case: EvalCase, result: CompletionResult) -> tuple[CriterionResult, str]:
    """Devuelve el resultado del criterio y la nota del caso.

    Segundo elemento: nota del criterio (si existe), que alimenta el reporte.
    """
    criteria = case.criteria
    note = criteria.note or ""
    if criteria.type == "deterministic_match":
        return deterministic_match(case.expected, result.raw_text, ignore_case=criteria.ignore_case), note
    if criteria.type == "json_match":
        return json_match(case.expected, result.raw_text), note
    if criteria.type == "schema_match":
        return schema_match(case.expected, result.raw_text, result.validation), note
    raise ValueError(f"criteria desconocido: {criteria.type}")


def run(
    dataset: EvalDataset,
    judge: Judge,
    *,
    mode: str = "smoke",
    threshold: float = 1.0,
) -> EvalReport:
    """Ejecuta un dataset de eval sobre el juez dado (cableado por el consumidor).

    - `mode`: 'smoke' (diario, barato) o 'full' (releases, cambios de prompt/modelo).
      El juez decide si usa replay (CI, determinista) o graba (record); el runner es agnóstico.
    - `threshold`: fracción [0, 1] de casos que deben pasar para que el eval esté OK.
    """
    cases: list[CaseResult] = []
    passed = 0
    cost = Decimal("0")

    for index, case in enumerate(dataset.cases, start=1):
        result = judge(case)
        cost += result.cost_usd
        criterion, note = _apply(case, result)
        ok = criterion.passed
        cases.append(
            CaseResult(
                index=index,
                passed=ok,
                detail=note or criterion.detail,
            )
        )
        if ok:
            passed += 1

    total = len(dataset.cases)
    pass_rate = passed / total if total else 0.0
    return EvalReport(
        prompt_id=dataset.prompt_id,
        prompt_version=dataset.prompt_version,
        mode=mode,
        threshold=threshold,
        total=total,
        passed=passed,
        pass_rate=pass_rate,
        threshold_ok=pass_rate >= threshold,
        cost_usd=cost,
        cases=cases,
    )