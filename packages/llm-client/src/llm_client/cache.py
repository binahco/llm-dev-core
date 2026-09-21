from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import CompletionRequest, CompletionResult


def cache_key(request: CompletionRequest, prompt_version: str) -> str:
    payload = {
        "prompt_id": request.prompt_id,
        "prompt_version": prompt_version,
        "model_alias": request.model_alias,
        "variables": request.variables,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class ResponseCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self._store: dict[str, CompletionResult] = {}
        self._path = Path(path) if path else None
        if self._path and self._path.is_file():
            self._load()

    def _load(self) -> None:
        for line in self._path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            self._store[data["key"]] = CompletionResult.model_validate(data["result"])

    def get(self, key: str) -> CompletionResult | None:
        return self._store.get(key)

    def put(self, key: str, result: CompletionResult) -> None:
        self._store[key] = result
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a") as handle:
                entry = json.dumps({"key": key, "result": result.model_dump()}, default=str)
                handle.write(entry + "\n")