from __future__ import annotations

from llm_client.models import TokenUsage
from llm_client.provider import ProviderRequest, ProviderResponse


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        text: str = "hola mundo",
        usage: TokenUsage | None = None,
        errors: list = (),
        stream_chunks: list[str] | None = None,
        interrupt_first_stream: bool = False,
    ) -> None:
        self.text = text
        self.usage = usage or TokenUsage(input_tokens=10, output_tokens=5)
        self.errors = list(errors)
        self.stream_chunks = stream_chunks or ["hola ", "mundo"]
        self.interrupt_first_stream = interrupt_first_stream
        self.complete_calls = 0
        self.stream_calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.complete_calls += 1
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        return ProviderResponse(text=self.text, model=request.model, usage=self.usage)

    def stream(self, request: ProviderRequest):
        self.stream_calls += 1
        if self.stream_calls == 1 and self.interrupt_first_stream:
            for chunk in self.stream_chunks:
                yield chunk
            raise RuntimeError("stream cortado tras el contenido")
        for chunk in self.stream_chunks:
            yield chunk


class SequentialValidator:
    def __init__(self, results) -> None:
        self._results = list(results)

    def __call__(self, text: str, schema: str | None):
        if len(self._results) > 1:
            return self._results.pop(0)
        return self._results[0]