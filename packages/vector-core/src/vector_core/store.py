"""Almacén en memoria con búsqueda por coseno (ADR-12)."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from .embed import EmbeddingProvider


class Scored(BaseModel):
    """Un resultado de búsqueda o par: quién y cuánto (coseno en [0, 1])."""

    id: str
    score: float = Field(ge=0.0, le=1.0)


def cosine(a: list[float], b: list[float]) -> float:
    """Coseno acotado a [0, 1] (los embeddings del módulo no son negativos)."""
    if len(a) != len(b):
        raise ValueError(f"dimensiones distintas: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return min(1.0, max(0.0, dot / (na * nb)))


class VectorStore:
    """Textos embebidos y comparables por coseno. En memoria, sin persistencia (§3)."""

    def __init__(self, embedder: EmbeddingProvider) -> None:
        self._embedder = embedder
        self._vectors: dict[str, list[float]] = {}

    def add(self, id: str, text: str) -> None:
        if id in self._vectors:
            raise ValueError(f"id duplicado: {id}")
        self._vectors[id] = self._embedder.embed(text)

    def search(self, text: str, *, top_k: int = 5, exclude: str | None = None) -> list[Scored]:
        """Top-k por coseno contra el texto consultado, sin el `exclude` (uno mismo)."""
        query = self._embedder.embed(text)
        resultados = [
            Scored(id=id_, score=round(cosine(query, vec), 4))
            for id_, vec in self._vectors.items()
            if id_ != exclude
        ]
        resultados.sort(key=lambda s: (-s.score, s.id))
        return resultados[:top_k]

    def pair(self, a: str, b: str) -> float:
        """Coseno entre dos textos ya almacenados, por id."""
        if a not in self._vectors or b not in self._vectors:
            raise KeyError(f"par desconocido: {a!r} / {b!r}")
        return cosine(self._vectors[a], self._vectors[b])

    def pairs(self, *, min_score: float = 0.0, top: int | None = None) -> list[Scored]:
        """Todos los pares (a < b) ordenados por coseno descendente."""
        ids = sorted(self._vectors)
        out: list[Scored] = []
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                score = round(cosine(self._vectors[a], self._vectors[b]), 4)
                if score >= min_score:
                    out.append(Scored(id=f"{a} ⟷ {b}", score=score))
        out.sort(key=lambda s: (-s.score, s.id))
        return out[:top] if top is not None else out

    def __len__(self) -> int:
        return len(self._vectors)
