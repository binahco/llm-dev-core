#!/usr/bin/env python3
"""collect_metrics.py — genera la página de evidencia (§10.1).

Contrato (se implementa en la semana 6 con ci-pack):
  - lee los `core-consumer.yml` → % de reutilización por semana;
  - lee los spans de `llm-client` → costo por proyecto y acumulado;
  - calcula cobertura de evals (prompts con dataset / prompts totales);
  - emite la matriz repo × versión-de-core;
  - escribe el dashboard en `docs/metrics/` / una URL publicada.

Estado actual: stub con firma definida. Deuda documentada hacia sem. 6.
"""

from __future__ import annotations


def collect(metrics_dir: str, spans_dir: str) -> dict:
    """Devuelve el dict con las métricas agregadas a partir de las fuentes."""
    raise NotImplementedError("ci-pack (sem. 6): implementar agregación de métricas")


def render(report: dict) -> str:
    """Devuelve la página HTML del dashboard de evidencia."""
    raise NotImplementedError("ci-pack (sem. 6): implementar render del dashboard")


if __name__ == "__main__":
    raise SystemExit("collect_metrics.py: stub de sem. 1, implementar en sem. 6")