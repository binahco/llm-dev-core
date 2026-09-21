from decimal import Decimal

import pytest
from llm_client import (
    CompletionRequest,
    CostCapExceeded,
    LlmClient,
    ResponseCache,
    TokenUsage,
    ValidationResult,
    Span,
)

from .conftest import FakeProvider, SequentialValidator


def _request(**overrides) -> CompletionRequest:
    base = dict(
        prompt_id="commit-message-generator",
        prompt_version="0.1.0",
        variables={"diff": "add foo"},
        model_alias="fast",
        tags=["commit-cli"],
    )
    base.update(overrides)
    return CompletionRequest(**base)


def test_complete_span_fields_ok() -> None:
    spans: list[Span] = []
    provider = FakeProvider(text="ok", usage=TokenUsage(input_tokens=10, output_tokens=5))
    client = LlmClient(provider, consumer_repo="commit-cli", emitter=lambda s, _r: spans.append(s))
    result = client.complete(_request())

    assert result.raw_text == "ok"
    assert result.validation.ok
    span = spans[0]
    assert span.span_id and span.trace_id
    assert span.consumer_repo == "commit-cli"
    assert span.prompt_id == "commit-message-generator"
    assert span.prompt_version == "0.1.0"
    assert span.model_alias == "fast"
    assert span.model == "big-pickle"
    assert span.provider == "fake"
    assert span.tokens_input == 10
    assert span.tokens_output == 5
    assert span.cost_usd == Decimal("0")
    assert span.latency_ms >= 0
    assert span.retry_count == 0
    assert span.cache_hit is False
    assert span.status == "ok"
    assert span.call_skipped is False
    assert span.retry_unnecessary is False
    assert span.error_type is None
    assert span.repaired_attempts == 0
    assert len(span.model_dump()) == 20
    assert span.as_jsonl().startswith("{")


def test_cache_hit_forces_call_skipped() -> None:
    spans: list[Span] = []
    cache = ResponseCache()
    provider = FakeProvider(text="ok")
    client = LlmClient(provider, consumer_repo="commit-cli", cache=cache, emitter=lambda s, _r: spans.append(s))

    first = client.complete(_request())
    second = client.complete(_request())

    assert provider.complete_calls == 1
    assert first.span_id == second.span_id
    span = spans[1]
    assert span.call_skipped is True
    assert span.cache_hit is True
    assert span.status == "skipped"
    assert span.latency_ms == 0


def test_retry_unnecessary_after_interrupted_stream() -> None:
    spans: list[Span] = []
    provider = FakeProvider(text="ok final", stream_chunks=["PERFECTO"], interrupt_first_stream=True)
    client = LlmClient(provider, consumer_repo="commit-cli", retry_base_ms=1, retry_jitter_ms=0, emitter=lambda s, _r: spans.append(s))

    result = client.stream(_request())

    assert result.raw_text == "PERFECTO"
    assert provider.stream_calls == 2
    span = spans[0]
    assert span.retry_count == 1
    assert span.retry_unnecessary is True
    assert span.status == "ok"


def test_transient_errors_retry_then_succeed() -> None:
    spans: list[Span] = []
    provider = FakeProvider(errors=[RuntimeError("boom"), RuntimeError("boom again"), None])
    client = LlmClient(provider, consumer_repo="opt", retry_base_ms=1, retry_jitter_ms=0, emitter=lambda s, _r: spans.append(s))

    result = client.complete(_request())

    assert result.validation.ok
    span = spans[0]
    assert span.retry_count == 2
    assert span.status == "ok"
    assert span.error_type is None


def test_repaired_after_validation_failure() -> None:
    spans: list[Span] = []
    provider = FakeProvider(text="respuesta")
    validator = SequentialValidator([ValidationResult(ok=False, errors=["schema invalido"]), ValidationResult(ok=True)])
    client = LlmClient(provider, validator=validator, retry_base_ms=1, retry_jitter_ms=0, emitter=lambda s, _r: spans.append(s))

    result = client.complete(_request())

    assert result.validation.ok
    span = spans[0]
    assert span.repaired_attempts == 1
    assert span.status == "repaired"


def test_validation_failure_exhausts_to_failed() -> None:
    spans: list[Span] = []
    provider = FakeProvider(text="mala")
    validator = SequentialValidator(
        [ValidationResult(ok=False, errors=["mal"]), ValidationResult(ok=False, errors=["mal"]), ValidationResult(ok=False, errors=["mal"])]
    )
    client = LlmClient(provider, validator=validator, repair_cap=2, retry_base_ms=1, retry_jitter_ms=0, emitter=lambda s, _r: spans.append(s))

    result = client.complete(_request())

    assert result.validation.ok is False
    span = spans[0]
    assert span.status == "failed"
    assert span.error_type == "validation"
    assert span.repaired_attempts == 2


def test_cost_cap_exceeded_blocks() -> None:
    spans: list[Span] = []
    client = LlmClient(
        FakeProvider(),
        cost_cap_usd=Decimal("0.10"),
        cost_fn=lambda *_: Decimal("0.5"),
        emitter=lambda s, _r: spans.append(s),
    )
    with pytest.raises(CostCapExceeded):
        client.complete(_request())
    assert spans[0].status == "blocked"
    assert spans[0].error_type == "cost_cap_exceeded"


def test_retries_exhausted_marks_failed() -> None:
    spans: list[Span] = []
    provider = FakeProvider(errors=[RuntimeError("x"), RuntimeError("x"), RuntimeError("x"), RuntimeError("x")])
    client = LlmClient(provider, retries=2, retry_base_ms=1, retry_jitter_ms=0, emitter=lambda s, _r: spans.append(s))

    result = client.complete(_request())

    assert provider.complete_calls == 4
    span = spans[0]
    assert span.status == "failed"
    assert span.error_type == "RuntimeError"