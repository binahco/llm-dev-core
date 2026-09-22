from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from llm_client import CostCapExceeded, LlmClient, TokenUsage
from llm_client.provider import ProviderRequest, ProviderResponse
from schema_validate import SchemaRegistry
from web_api_base import CompleteRequest, create_app, error_status, llm_complete, sse_response


class StubProvider:
    name = "stub"

    def __init__(self, text: str, usage: TokenUsage | None = None) -> None:
        self.text = text
        self.usage = usage or TokenUsage(input_tokens=10, output_tokens=5)
        self.complete_calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.complete_calls += 1
        return ProviderResponse(text=self.text, model=request.model, usage=self.usage)

    def stream(self, request: ProviderRequest):
        yield self.text


class Proyecto(BaseModel):
    nombre: str
    exitoso: bool


def _build_client(provider: StubProvider, *, cost_cap=None, cost_fn=None, validator=None, renderer=None) -> LlmClient:
    registry = SchemaRegistry()
    registry.register("proyecto-v1", Proyecto)
    kwargs = {}
    if cost_cap is not None:
        kwargs["cost_cap_usd"] = cost_cap
    if cost_fn is not None:
        kwargs["cost_fn"] = cost_fn
    return LlmClient(
        provider,
        consumer_repo="web_api_base_tests",
        model_aliases={"fast": "opencode/teste"},
        validator=validator or registry.make_validator("proyecto-v1"),
        renderer=renderer,
        **kwargs,
    )


_GOOD_JSON = '{"nombre": "seed-6", "exitoso": true}'
_VALID_REQUEST = {"prompt_id": "p", "variables": {"x": 1}, "model_alias": "fast", "response_schema": "proyecto-v1"}


def test_health() -> None:
    client = _build_client(StubProvider(text=_GOOD_JSON))
    app = create_app("eval-api tests", "0.1.0", client=client)
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "eval-api tests"
    assert body["provider"] == "stub"
    assert body["model_alias"] == ["fast"]


def test_llm_endpoint_returns_validated_json() -> None:
    provider = StubProvider(text=_GOOD_JSON)
    client = _build_client(provider)
    app = create_app("s", "0", client=client)
    resp = TestClient(app).post("/llm", json=_VALID_REQUEST)
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation_ok"] is True
    assert body["parsed"] == {"nombre": "seed-6", "exitoso": True}
    assert body["prompt_id"] == "p"
    assert Decimal(body["cost_usd"]) == 0
    assert provider.complete_calls == 1


def test_llm_endpoint_blocks_unvalidated_output() -> None:
    client = _build_client(StubProvider(text="no es json"))
    app = create_app("s", "0", client=client)
    resp = TestClient(app).post("/llm", json=_VALID_REQUEST)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "salida_no_validada"


def test_llm_endpoint_cost_cap_maps_to_429() -> None:
    expensive = lambda _m, _i, _o: Decimal("0.5")
    client = _build_client(StubProvider(text=_GOOD_JSON), cost_cap=Decimal("0.1"), cost_fn=expensive)
    app = create_app("s", "0", client=client)
    resp = TestClient(app).post("/llm", json=_VALID_REQUEST)
    assert resp.status_code == 429
    assert resp.json()["error"] == "presupuesto_excedido"


def test_llm_endpoint_invalid_schema_request_422() -> None:
    client = _build_client(StubProvider(text=_GOOD_JSON))
    app = create_app("s", "0", client=client)
    resp = TestClient(app).post("/llm", json={"prompt_id": "p", "response_schema": 123})
    assert resp.status_code == 422


def test_error_status_mappings() -> None:
    status, code, detail = error_status(CostCapExceeded("0.5", "0.1", "z"))
    assert status == 429
    assert code == "presupuesto_excedido"
    status, code, detail = error_status(RuntimeError("boom"))
    assert status == 500
    assert code == "error_interno"


def test_llm_complete_without_schema_skips_gate() -> None:
    client = _build_client(StubProvider(text="texto libre"))
    request = CompleteRequest(prompt_id="p", variables={"x": 1}, model_alias="fast", response_schema=None)
    body = llm_complete(client, request, require_valid=False)
    assert body["validation_ok"] is True
    assert body["parsed"] is None
    assert body["content"] == "texto libre"


def test_sse_response_renderer() -> None:
    import asyncio

    client = _build_client(StubProvider(text=_GOOD_JSON))
    app = create_app("s", "0", client=client)
    stream = sse_response(client, CompleteRequest.model_validate(_VALID_REQUEST))
    assert stream.media_type == "text/event-stream"

    async def _drain():
        return [chunk async for chunk in stream.body_iterator]

    events = [line for line in asyncio.run(_drain()) if line.startswith("data:")]
    assert len(events) == 1
    payload = json.loads(events[0][5:])
    assert payload["parsed"] == {"nombre": "seed-6", "exitoso": True}


def test_health_extra_fields() -> None:
    client = _build_client(StubProvider(text=_GOOD_JSON))
    app = create_app("s", "0", client=client, health_extra={"version": "0.1.0"})
    body = TestClient(app).get("/health").json()
    assert body["version"] == "0.1.0"


def test_disabled_llm_endpoint() -> None:
    client = _build_client(StubProvider(text=_GOOD_JSON))
    app = create_app("s", "0", client=client, enable_llm_endpoint=False)
    resp = TestClient(app).post("/llm", json=_VALID_REQUEST)
    assert resp.status_code == 404