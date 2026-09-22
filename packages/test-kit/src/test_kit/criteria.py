from __future__ import annotations

import re

from llm_client import ValidationResult
from pydantic import BaseModel

from schema_validate import extract_json


class CriterionResult(BaseModel):
    passed: bool
    detail: str


def normalize(text: str, *, ignore_case: bool = False) -> str:
    """Colapsa espacios y normaliza el caso para comparaciones deterministas."""
    collapsed = " ".join(re.split(r"\s+", str(text).strip()))
    return collapsed.lower() if ignore_case else collapsed


def deterministic_match(expected, raw_text: str, *, ignore_case: bool = False) -> CriterionResult:
    exp = normalize(expected, ignore_case=ignore_case)
    got = normalize(raw_text, ignore_case=ignore_case)
    return CriterionResult(
        passed=exp == got,
        detail="" if exp == got else f"esperado {exp!r} ≠ salida {got!r}",
    )


def json_match(expected, raw_text: str) -> CriterionResult:
    try:
        got = extract_json(raw_text)
    except (ValueError, TypeError) as exc:
        return CriterionResult(passed=False, detail=f"JSON inválido: {exc}")
    passed = got == expected
    return CriterionResult(
        passed=passed,
        detail="" if passed else f"JSON ≠ esperado (salida={got!r})",
    )


def schema_match(expected, raw_text: str, validation: ValidationResult) -> CriterionResult:
    if not validation.ok:
        return CriterionResult(passed=False, detail="; ".join(validation.errors))
    if expected is not None:
        parsed = validation.parsed
        passed = _deep_equal(parsed, expected)
        return CriterionResult(
            passed=passed,
            detail="" if passed else f"estructura válida pero ≠ expected ({parsed!r})",
        )
    return CriterionResult(passed=True, detail="")


def _deep_equal(a, b) -> bool:
    if isinstance(a, BaseModel):
        a = a.model_dump()
    if isinstance(b, BaseModel):
        b = b.model_dump()
    return a == b