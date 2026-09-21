from __future__ import annotations

from typing import Callable

from llm_client import ValidationResult
from pydantic import BaseModel

from .validate import M, SchemaNotFound, validate_text

Validator = Callable[[str, str | None], ValidationResult]


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[str, type[BaseModel]] = {}

    def register(self, schema_id: str, model: type[M]) -> None:
        self._schemas[schema_id] = model

    def get(self, schema_id: str) -> type[BaseModel]:
        try:
            return self._schemas[schema_id]
        except KeyError:
            raise SchemaNotFound(schema_id) from None

    def make_validator(self, schema_id: str) -> Validator:
        """Devuelve un callable válido para el hook `validator` de llm-client."""
        model = self.get(schema_id)

        def validator(text: str, schema: str | None = None) -> ValidationResult:
            return validate_text(model, text)

        return validator


default_registry = SchemaRegistry()


def register(schema_id: str, model: type[M]) -> None:
    default_registry.register(schema_id, model)


def make_validator(schema_id: str) -> Validator:
    return default_registry.make_validator(schema_id)