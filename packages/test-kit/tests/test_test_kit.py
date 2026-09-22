from __future__ import annotations

from decimal import Decimal

import pytest
from llm_client import CompletionResult, TokenUsage, ValidationResult
from pydantic import BaseModel
from test_kit import (
    DatasetError,
    EvalCase,
    EvalDataset,
    EvalReport,
    deterministic_match,
    json_match,
    run,
    schema_match,
)

SCHEMA_ID = "eval-demo-v1"


class Demo(BaseModel):
    summary: str
    ok: bool


def _result(raw_text: str, *, cost: Decimal = Decimal("0"), validation: ValidationResult | None = None) -> CompletionResult:
    return CompletionResult(
        raw_text=raw_text,
        parsed=Demo.model_validate(raw_text) if validation and validation.ok else None,
        validation=validation or ValidationResult(ok=True),
        usage=TokenUsage(input_tokens=1, output_tokens=1),
        cost_usd=cost,
        latency_ms=1,
        prompt_id="x",
        prompt_version="0.1.0",
        model_alias="fast",
        model="demo",
        provider="stub",
        span_id="s",
    )


def _case(criteria: dict, *, expected=None) -> EvalCase:
    return EvalCase(
        prompt_id="prompt-demo",
        prompt_version="0.1.0",
        input={},
        expected=expected,
        criteria=criteria,
    )


def _dataset(tmp_path, lines: list[str]) -> EvalDataset:
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(lines) + "\n")
    return EvalDataset.from_jsonl(path)


def test_from_jsonl_ok(tmp_path) -> None:
    ds = _dataset(
        tmp_path,
        [
            '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"expected":"feat: x","criteria":{"type":"deterministic_match"}}',
            '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"expected":"feat: y","criteria":{"type":"deterministic_match"}}',
        ],
    )
    assert ds.prompt_id == "p"
    assert len(ds.cases) == 2


def test_from_jsonl_malformed(tmp_path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text('{"prompt_id": broken\n')
    with pytest.raises(DatasetError, match="JSON inválido"):
        EvalDataset.from_jsonl(path)


def test_from_jsonl_mixed_prompts(tmp_path) -> None:
    with pytest.raises(DatasetError, match="mezclados"):
        _dataset(
            tmp_path,
            [
                '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"criteria":{"type":"deterministic_match"}}',
                '{"prompt_id":"q","prompt_version":"0.1.0","input":{},"criteria":{"type":"deterministic_match"}}',
            ],
        )


def test_from_jsonl_empty(tmp_path) -> None:
    with pytest.raises(DatasetError, match="vacío"):
        _dataset(tmp_path, [])


def test_from_jsonl_missing_file(tmp_path) -> None:
    with pytest.raises(DatasetError, match="no encontrado"):
        EvalDataset.from_jsonl(tmp_path / "no-existe.jsonl")


def test_deterministic_match_normalizes() -> None:
    ok = deterministic_match("feat: add retry", "  feat:  add   retry  ")
    assert ok.passed is True
    case_sensitive = deterministic_match("Feat: x", "feat: x")
    assert case_sensitive.passed is False
    ignore = deterministic_match("Feat: x", "feat: x", ignore_case=True)
    assert ignore.passed is True


def test_json_match_handles_fences() -> None:
    result = json_match({"a": 1}, "responde con:\n```json\n{\"a\": 1}\n```\n")
    assert result.passed is True
    wrong = json_match({"a": 1}, "```json\n{\"a\": 2}\n```")
    assert wrong.passed is False


def test_schema_match_valid_against_expected() -> None:
    from test_kit.criteria import schema_match as sm

    validation = ValidationResult(ok=True, parsed=Demo(summary="todo bien", ok=True))
    result = sm({"summary": "todo bien", "ok": True}, '{"summary": "todo bien", "ok": true}', validation)
    assert result.passed is True


def test_schema_match_reports_errors() -> None:
    from test_kit.criteria import schema_match as sm

    validation = ValidationResult(ok=False, errors=["summary: campo faltante"])
    result = sm(None, '{"ok": true}', validation)
    assert result.passed is False
    assert "campo faltante" in result.detail


def test_run_pass_threshold_and_cost(tmp_path) -> None:
    ds = _dataset(
        tmp_path,
        [
            '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"expected":"feat: x","criteria":{"type":"deterministic_match"}}',
            '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"expected":"feat: y","criteria":{"type":"deterministic_match"}}',
        ],
    )

    def judge(case: EvalCase) -> CompletionResult:
        return _result(case.expected, cost=Decimal("0.01"))

    report = run(ds, judge, mode="smoke", threshold=1.0)
    assert isinstance(report, EvalReport)
    assert report.total == 2
    assert report.passed == 2
    assert report.pass_rate == 1.0
    assert report.threshold_ok is True
    assert report.cost_usd == Decimal("0.02")
    assert report.mode == "smoke"


def test_run_fails_below_threshold(tmp_path) -> None:
    ds = _dataset(
        tmp_path,
        [
            '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"expected":"feat: x","criteria":{"type":"deterministic_match"}}',
            '{"prompt_id":"p","prompt_version":"0.1.0","input":{},"expected":"feat: y","criteria":{"type":"deterministic_match"}}',
        ],
    )

    def judge(case: EvalCase) -> CompletionResult:
        return _result("respuesta incorrecta")

    report = run(ds, judge, mode="full", threshold=1.0)
    assert report.passed == 0
    assert report.threshold_ok is False
    assert report.pass_rate == 0.0