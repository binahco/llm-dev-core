from __future__ import annotations

from typing import Iterator

import httpx

from ..models import TokenUsage
from ..provider import ProviderRequest, ProviderResponse


class OpenAICompatible:
    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._client = client or httpx.Client(timeout=60)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, request: ProviderRequest, stream: bool) -> dict:
        payload = {
            "model": request.model or self.model,
            "messages": request.messages,
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        response = self._client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._payload(request, stream=False),
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage")
        tokens = (
            TokenUsage(
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
            )
            if usage
            else None
        )
        return ProviderResponse(
            text=text,
            model=data.get("model", request.model),
            usage=tokens,
        )

    def stream(self, request: ProviderRequest) -> Iterator[str]:
        with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._payload(request, stream=True),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                data = __import__("json").loads(chunk)
                delta = data["choices"][0]["delta"].get("content")
                if delta:
                    yield delta