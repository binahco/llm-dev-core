from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from llm_client import ValidationResult
from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)


class SchemaNotFound(KeyError):
    def __init__(self, schema_id: str) -> None:
        super().__init__(f"schema no registrado: {schema_id!r}")
        self.schema_id = schema_id


def strip_json_fence(text: str) -> str:
    """Quita caretas ```json … ``` cuando el modelo las añade (JSON mode no las garantiza)."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def extract_json(text: str) -> Any:
    """Parsea JSON: con fences, sin fences, o recortando al primer/last '{'/'['."""
    candidate = strip_json_fence(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    start = min(
        (candidate.find(ch) for ch in "{[" if candidate.find(ch) != -1),
        default=-1,
    )
    end = max(
        (candidate.rfind(ch) for ch in "}]" if candidate.rfind(ch) != -1),
        default=-1,
    )
    if start == -1 or end <= start:
        raise ValueError("no se encontró JSON en la respuesta")
    return json.loads(candidate[start : end + 1])


def _describe_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for entry in exc.errors():
        loc = ".".join(str(part) for part in entry.get("loc", ())) or "<raiz>"
        errors.append(f"{loc}: {entry.get('msg')}")
    return errors


def validate_text(model: type[M], text: str) -> ValidationResult:
    """Valida el texto crudo del LLM contra un modelo Pydantic.

    Devuelve un ValidationResult (contrato de llm-client) con `parsed` poblado
    solo cuando la validación pasa.
    """
    try:
        data = extract_json(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return ValidationResult(ok=False, errors=[f"JSON inválido: {exc}"])
    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=_describe_errors(exc))
    return ValidationResult(ok=True, errors=[], parsed=parsed)