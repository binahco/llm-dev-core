from __future__ import annotations

from typing import Any

import pytest
from llm_client import CompletionRequest, LlmClient
from llm_client.models import TokenUsage
from llm_client.provider import ProviderRequest, ProviderResponse
from pydantic import BaseModel

from schema_validate import SchemaNotFound, make_validator, register, validate_text
from schema_validate.registry import SchemaRegistry
from schema_validate.validate import extract_json, strip_json_fence


class Change(BaseModel):
    type: str
    scope: str | None = None
    description: str
    breaking: bool = False


class ReleaseNotes(BaseModel):
    version: str
    title: str
    changes: list[Change]


def test_validate_text_ok_parses_model() -> None:
    result = validate_text(
        ReleaseNotes,
        '{"version": "0.2.0", "title": "Retry", "changes": [{"type": "feat", "description": "backoff"}]}',
    )
    assert result.ok is True
    assert result.errors == []
    assert isinstance(result.parsed, ReleaseNotes)
    assert result.parsed.title == "Retry"


def test_validate_text_strips_code_fences() -> None:
    text = 'claro, aquí tienes:\n```json\n{"version": "1.0.0", "title": "x", "changes": []}\n```'
    result = validate_text(ReleaseNotes, text)
    assert result.ok is True
    assert isinstance(result.parsed, ReleaseNotes)


def test_validate_text_reports_field_errors() -> None:
    text = '{"version": "0.2.0", "title": 123, "changes": [{"type": "feat", "description": "ok"}]}'
    result = validate_text(ReleaseNotes, text)
    assert result.ok is False
    assert any("title" in err for err in result.errors)
    assert result.parsed is None


def test_validate_text_json_invalido() -> None:
    result = validate_text(ReleaseNotes, "esto no es JSON en absoluto")
    assert result.ok is False
    assert result.errors[0].startswith("JSON inválido")


def test_extract_json_from_fenced_plain_text() -> None:
    assert strip_json_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    data = extract_json('por aquí:\n{"a": [1, 2, 3]}\nfin')
    assert data == {"a": [1, 2, 3]}


def test_registry_make_validator_via_factory() -> None:
    registry = SchemaRegistry()
    registry.register("release-notes-v1", ReleaseNotes)
    validator = registry.make_validator("release-notes-v1")
    result = validator('{"version": "0.3.0", "title": "t", "changes": []}', "release-notes-v1")
    assert result.ok is True
    assert isinstance(result.parsed, ReleaseNotes)
    with pytest.raises(SchemaNotFound):
        registry.get("nope")


def test_default_registry_register() -> None:
    register("legacy", ReleaseNotes)
    validator = make_validator("legacy")
    assert validator("x").ok is False


class SequenceProvider:
    name = "fake"

    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        return ProviderResponse(
            text=text,
            model=request.model,
            usage=TokenUsage(input_tokens=10, output_tokens=5),
        )

    def stream(self, request: ProviderRequest):
        raise NotImplementedError


def _renderer(_prompt_id: str, _version: str, _variables: dict[str, Any]) -> list[dict]:
    return [{"role": "user", "content": "genera release notes JSON"}]


def _run_client(provider, *, validator) -> tuple[LlmClient, CompletionRequest, list]:
    spans: list = []

    def emitter(span, _result) -> None:
        spans.append(span)

    client = LlmClient(
        provider,
        consumer_repo="release-scribe",
        model_aliases={"fast": "big-pickle"},
        validator=validator,
        renderer=_renderer,
        emitter=emitter,
    )
    request = CompletionRequest(
        prompt_id="release-notes-generator",
        prompt_version="0.1.0",
        variables={},
        model_alias="fast",
        response_schema="release-notes-v1",
    )
    return client, request, spans


def test_llm_client_repair_loop_populates_parsed() -> None:
    registry = SchemaRegistry()
    registry.register("release-notes-v1", ReleaseNotes)
    valid = '{"version": "0.3.0", "title": "Lo mismo", "changes": [{"type": "fix", "description": "a", "breaking": true}]}'
    provider = SequenceProvider(["no es json", valid])
    client, request, spans = _run_client(provider, validator=registry.make_validator("release-notes-v1"))

    result = client.complete(request)

    assert result.validation.ok is True
    assert result.parsed is not None
    assert isinstance(result.parsed, ReleaseNotes)
    assert result.parsed.changes[0].breaking is True
    assert provider.calls == 2
    span = spans[0]
    assert span.status == "repaired"
    assert span.repaired_attempts == 1


def test_llm_client_validation_failed_after_cap() -> None:
    registry = SchemaRegistry()
    registry.register("release-notes-v1", ReleaseNotes)
    provider = SequenceProvider(["aaa", "bbb", "ccc"])
    client, request, spans = _run_client(provider, validator=registry.make_validator("release-notes-v1"))

    result = client.complete(request)

    assert result.validation.ok is False
    assert result.parsed is None
    span = spans[0]
    assert span.status == "failed"
    assert span.repaired_attempts == 2
    assert span.error_type == "validation"