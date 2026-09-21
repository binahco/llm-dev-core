#!/usr/bin/env python3
"""check_consumers.py — valida la cadena de consumidores del core.

Contrato (se implementa en la semana 6 con ci-pack):
  - cada repo del topic `llm-dev-consumer` tiene `core-consumer.yml`;
  - el manifest declara `core_version`, `reused_modules`, `new_surface`
    y `estimated_new_surface`;
  - lint anti-imports: ninguno por fuera de `llm-client`/paquetes del core;
  - lint anti-prompts inline + frontmatter obligatorio.

Estado actual: stub con firma definida. Deuda documentada hacia sem. 6.
"""

from __future__ import annotations

import sys


def check_manifest(path: str) -> list[str]:
    """Devuelve la lista de errores del manifest en `path`. Vacía si es válido."""
    raise NotImplementedError("ci-pack (sem. 6): implementar validación del manifest")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("uso: check_consumers.py <repo_o_manifest> ...", file=sys.stderr)
        return 2
    for target in argv:
        for error in check_manifest(target):
            print(f"{target}: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())