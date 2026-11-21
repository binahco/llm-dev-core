"""vector-core — embedder inyectable y búsqueda por coseno (ADR-12).

La regla de honestidad del módulo: el embedder por defecto es **léxico** (bolsa de
palabras hasheada), no semántico. `opencode/big-pickle` no expone embeddings (verificado
en la sem. 23), así que aquí no se finge significado: se vectoriza vocabulario. Cuando
exista un embedder real, se inyecta por el protocolo y el store no cambia.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_DIMS_MIN = 16


def _terms(text: str) -> list[str]:
    raw = re.split(r"[^a-záéíóúüñ0-9]+", text.lower())
    return [t for t in raw if len(t) >= 3]


class EmbeddingProvider(Protocol):
    """El punto de injerto: cualquier embedder determinista entra por aquí."""

    dims: int

    def embed(self, text: str) -> list[float]: ...


class LexicalEmbedder:
    """Bolsa de palabras hasheada a `dims` dimensiones, normalizada L2.

    Determinista por construcción (D4): el hash es sha256 con semilla implícita fija —
    nunca el `hash()` nativo de Python, que va salado por proceso. Dos textos con el
    mismo vocabulario caen en el mismo vector; sin vocabulario compartido, coseno ~0
    (salvo colisión de hash, que se acota con `dims`).
    """

    def __init__(self, dims: int = 256) -> None:
        if dims < _DIMS_MIN:
            raise ValueError(f"dims debe ser >= {_DIMS_MIN}, recibido {dims!r}")
        self.dims = dims

    def _slot(self, term: str) -> int:
        digest = hashlib.sha256(f"vector-core:{term}".encode()).digest()
        return int.from_bytes(digest[:8], "big") % self.dims

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for term in _terms(text):
            vec[self._slot(term)] += 1.0
        norma = math.sqrt(sum(v * v for v in vec))
        if norma == 0.0:
            return vec
        return [v / norma for v in vec]
