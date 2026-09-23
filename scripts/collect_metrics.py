#!/usr/bin/env python3
"""collect_metrics.py — página de evidencia (§10.1). Implementado con ci-pack (sem. 7).

Uso:
  collect_metrics.py [--spans RUTA_SPANS] CONSUMIDOR ...
  collect_metrics.py --self-auto   # detecta consumidores en ../ y spans en ./spans
                                   # (en CI sin consumidores genera evidencia vacía, exit 0)

Escribe `docs/metrics/evidence.html` y devuelve 0.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ci_pack import collect, render

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "metrics" / "evidence.html"
SPANS_DEFAULT = ROOT.parent  # los repos de consumidores viven al lado del core


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consumers", nargs="*", help="rutas a repos consumidores")
    parser.add_argument("--spans", default=None, help="directorio raíz donde buscar spans/ por repo")
    parser.add_argument("--self-auto", action="store_true", help="detecta consumidores en ../ y spans adyacantes")
    args = parser.parse_args(argv)

    repos: list[Path] = []
    if args.self_auto:
        for p in ROOT.parent.iterdir():
            if p.is_dir() and (p / "core-consumer.yml").is_file():
                repos.append(p)
        spans_dir = None
    else:
        repos = [Path(c) for c in args.consumers]
        spans_dir = Path(args.spans) if args.spans else None

    if not repos:
        if args.self_auto:
            print("collect_metrics: sin consumidores en ../ — evidencia vacía (exit 0)")
            OUT.write_text(render(collect([], spans_dir=None)))
            return 0
        parser.print_usage(sys.stderr)
        return 2

    report = collect(repos, spans_dir=spans_dir)
    OUT.write_text(render(report))
    print(f"evidence: {report.repo_count} consumidores, ${report.total_cost_usd:.4f} acumulado → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())