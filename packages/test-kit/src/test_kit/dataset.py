from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetError(ValueError):
    """Dataset de eval mal formado: JSON inválido, campos faltantes o prompt_ids mezclados."""


class Criterion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["deterministic_match", "json_match", "schema_match"]
    schema_id: str | None = Field(default=None, validation_alias="schema", serialization_alias="schema")
    ignore_case: bool = False
    note: str | None = None


class EvalCase(BaseModel):
    prompt_id: str
    prompt_version: str
    input: dict[str, Any]
    expected: Any = None
    criteria: Criterion


class EvalDataset(BaseModel):
    prompt_id: str
    prompt_version: str
    cases: list[EvalCase] = Field(default_factory=list)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "EvalDataset":
        p = Path(path)
        try:
            lines = p.read_text().splitlines()
        except FileNotFoundError as exc:
            raise DatasetError(f"{p}: fichero no encontrado") from exc
        cases: list[EvalCase] = []
        for lineno, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{p}:{lineno}: JSON inválido: {exc}") from exc
            cases.append(EvalCase.model_validate(raw))

        if not cases:
            raise DatasetError(f"{p}: dataset vacío")

        first = cases[0]
        for case in cases[1:]:
            if (case.prompt_id, case.prompt_version) != (first.prompt_id, first.prompt_version):
                raise DatasetError(
                    f"{p}: prompt_id/version mezclados (esperaba {first.prompt_id}@{first.prompt_version})"
                )

        return cls(prompt_id=first.prompt_id, prompt_version=first.prompt_version, cases=cases)