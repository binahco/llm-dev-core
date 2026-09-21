import json

import httpx
import pytest
from llm_client import CompletionRequest, LlmClient
from llm_client.provider import ProviderRequest
from llm_client.providers.openai_compat import OpenAICompatible


def _transport(payload: dict | list, stream: bool = False) -> httpx.MockTransport:
    if stream:
        lines = "".join(
            f"data: {json.dumps(chunk)}\n"
            for chunk in payload
        ) + "data: [DONE]\n"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=lines, headers={"Content-Type": "text/event-stream"})

    else:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def _client(transport) -> LlmClient:
    inner = OpenAICompatible(base_url="https://mock", client=httpx.Client(transport=transport))
    return LlmClient(inner)


def _request() -> CompletionRequest:
    return CompletionRequest(prompt_id="p", model_alias="fast", variables={})


def test_openai_compatible_complete_parses_usage() -> None:
    payload = {
        "choices": [{"message": {"content": "feat: add foo"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        "model": "gpt-4o-mini",
    }
    client = _client(_transport(payload))
    result = client.complete(_request())

    assert result.raw_text == "feat: add foo"
    assert result.usage.input_tokens == 3
    assert result.usage.output_tokens == 2
    assert result.model == "big-pickle"
    assert result.provider == "openai-compatible"


def test_openai_compatible_stream_parses_deltas() -> None:
    chunks = [
        {"choices": [{"delta": {"content": "feat: "}}]},
        {"choices": [{"delta": {"content": "add foo"}}]},
        {"choices": [{"delta": {}}]},
    ]
    client = _client(_transport(chunks, stream=True))
    result = client.stream(_request())

    assert result.raw_text == "feat: add foo"


def test_openai_compatible_sends_bearer_and_model() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "model": "m"})

    provider = OpenAICompatible(
        base_url="https://mock",
        api_key="key-123",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    request = ProviderRequest(model="big-pickle", messages=[{"role": "user", "content": "hola"}])
    provider.complete(request)

    assert captured["auth"] == "Bearer key-123"
    assert captured["model"] == "big-pickle"