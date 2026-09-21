from __future__ import annotations

import json
from pathlib import Path

from .provider import Provider, ProviderRequest, ProviderResponse


class ReplayProvider:
    name = "replay"

    def __init__(
        self,
        cassette_dir: str | Path,
        *,
        record: bool = False,
        inner: Provider | None = None,
    ) -> None:
        self.dir = Path(cassette_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.record = record
        self.inner = inner

    def _cassette(self, request: ProviderRequest, stream: bool) -> Path:
        safe_model = request.model.replace("/", "--")
        slug = f"{'stream' if stream else 'complete'}-{safe_model}-{len(request.messages)}"
        return self.dir / f"{slug}.jsonl"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        if not self.record:
            entry = self._read(self._cassette(request, stream=False), request)
            return ProviderResponse.model_validate(entry["response"])
        if self.inner is None:
            raise RuntimeError("ReplayProvider en modo record requiere inner")
        response = self.inner.complete(request)
        self._append(self._cassette(request, stream=False), request, response)
        return response

    def stream(self, request: ProviderRequest) -> list[str]:
        if not self.record:
            entry = self._read(self._cassette(request, stream=True), request)
            return list(entry["chunks"])
        if self.inner is None:
            raise RuntimeError("ReplayProvider en modo record requiere inner")
        chunks = list(self.inner.stream(request))
        self._append_chunks(self._cassette(request, stream=True), request, chunks)
        return chunks

    def _read(self, path: Path, request: ProviderRequest) -> dict:
        if not path.is_file():
            raise FileNotFoundError(f"cassette no encontrado: {path}")
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry["request"] == request.messages and entry.get("model") == request.model:
                return entry
        raise KeyError(f"cassette sin entrada para el request: {path}")

    def _append(self, path: Path, request: ProviderRequest, response: ProviderResponse) -> None:
        with path.open("a") as handle:
            entry = {"model": request.model, "request": request.messages, "response": response.model_dump()}
            handle.write(json.dumps(entry, default=str) + "\n")

    def _append_chunks(self, path: Path, request: ProviderRequest, chunks: list[str]) -> None:
        with path.open("a") as handle:
            entry = {"model": request.model, "request": request.messages, "chunks": chunks}
            handle.write(json.dumps(entry, default=str) + "\n")