from __future__ import annotations

import json
import subprocess
from typing import Iterator

from ..models import TokenUsage
from ..provider import ProviderRequest, ProviderResponse


class OpenCodeCLI:
    name = "opencode"

    def __init__(self, model: str, *, cwd: str | None = None, binary: str = "opencode") -> None:
        self.model = model
        self.cwd = cwd
        self.binary = binary

    @staticmethod
    def _render_prompt(request: ProviderRequest) -> str:
        return "\n\n".join(f"{m['role']}:\n{m['content']}" for m in request.messages)

    def _spawn(self, prompt: str) -> subprocess.Popen:
        cmd = [self.binary, "run", "--format", "json", "--model", self.model, prompt]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=self.cwd,
        )

    @staticmethod
    def _parse(line: str) -> tuple[str, int | None, str | None]:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            return "", None, None
        event_type = event.get("type")
        part = event.get("part") or {}
        if part.get("type") == "text":
            return part.get("text", ""), None, None
        if event_type in ("step-finish", "step_finish"):
            tokens = part.get("tokens") or {}
            input_tokens = tokens.get("input")
            output_tokens = tokens.get("output")
            if input_tokens is not None and output_tokens is not None:
                usage = {"input": input_tokens, "output": output_tokens}
                return "", usage, part.get("cost")
        return "", None, None

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        proc = self._spawn(self._render_prompt(request))
        text_parts: list[str] = []
        usage: TokenUsage | None = None
        for line in iter(proc.stdout.readline, ""):
            current, usage_data, _ = self._parse(line)
            if current:
                text_parts.append(current)
            if usage_data:
                usage = TokenUsage(input_tokens=usage_data["input"], output_tokens=usage_data["output"])
        proc.wait()
        return ProviderResponse(text="".join(text_parts), model=self.model, usage=usage)

    def stream(self, request: ProviderRequest) -> Iterator[str]:
        proc = self._spawn(self._render_prompt(request))
        try:
            for line in proc.stdout:
                current, _, _ = self._parse(line)
                if current:
                    yield current
        finally:
            proc.wait()