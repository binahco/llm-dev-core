#!/usr/bin/env python3
"""verification_perf — baseline de rendimiento del core (METODOLOGIA §7).

Hasta v1.1 "optimizado" no tenía oráculo: el baseline de contratos mide forma, no
velocidad (§4). Este script mide la velocidad bajo las tres reglas de §7: la forma es
contrato (el coste de una operación O(1) no crece con el estado), los pisos de
guardarrail viven ~100× por debajo de lo medido, y la deuda se publica en `FALSE`
en vez de fingirse verde.

Escribe `docs/verification/{perf.json,PERF.md}`. Ninguna cifra del informe está
escrita a mano: veredictos y evidencia se derivan de la medición. Las cláusulas son
`CRITERIO DE PROYECTO` y viven en `docs/verification/METODOLOGIA.md` §7; sus anclas
se registran en `scripts/verification_clauses.py` como las del baseline.

A diferencia del baseline de contratos, el JSON de perf **no** es reproducible byte a
byte (los tiempos cambian por corrida): no hay test de sync exacto, pero la suite
exige estructura, veredictos derivados y cláusulas ancladas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT.parent
CONSUMERS = [
    "commit-cli",
    "release-scribe",
    "sec-check",
    "bench-runner",
    "eval-api",
    "ci-scribe",
    "llm-gateway",
    "fleet-bot",
    "content-ray",
    "evidence-api",
    "docs-gen",
    "core-smoke",
]

REPS = 3  # mejor de REPS corridas: amortigua el ruido del scheduler, no lo elimina.

# Pisos de guardarrail (§7.2): ~1/100 de lo medido al escribir este script. Un piso
# no dice "es rápido"; dice "no se volvió grotescamente lento".
PISO_PARSER_DOCS_S = 40
PISO_DETECT_LINES_S = 3_500
PISO_VALIDATE_S = 5_000
PISO_SPAN_S = 3_000
PISO_PRICE_KEY_S = 75_000
PISO_RATELIMITER_S = 60_000

# Cláusula de forma (§7.1): el hit de cache debe costar lo mismo gordo o flaco el store.
CACHE_STORE_GRANDE = 2_500
CACHE_HITS = 2_000
UMBRAL_RATIO_HIT = 10

N_VALIDATE = 2_000
N_SPAN = 5_000
N_PRICE_KEY = 5_000
N_RATELIMITER = 10_000


# --------------------------------------------------------------------------
# utilidades compartidas con el baseline (corpus idéntico, exclusión idéntica)
# --------------------------------------------------------------------------
def _corpus() -> list[Path]:
    """Documentos reales que `parser-io` acepta: ADRs, READMEs, prompts y plantillas."""
    files: list[Path] = sorted((ROOT / "docs" / "decisions").glob("*.md"))
    files.append(ROOT / "ARCHITECTURE.md")
    files.append(ROOT / "README.md")
    files.append(ROOT / "CHANGELOG.md")
    files.extend(sorted((ROOT / "templates").glob("*.md")))
    # `docs/verification/` queda fuera: la medición no puede incluir su propia salida.
    fuera = (ROOT / "docs" / "verification").resolve()
    for name in CONSUMERS:
        repo = PROJECTS / name
        for candidate in (repo / "README.md", *sorted(repo.glob("prompts/*.md"))):
            if candidate.is_file():
                files.append(candidate)
    files.extend(f for f in sorted((ROOT / "docs").rglob("*.md")) if fuera not in f.resolve().parents)
    return sorted({f for f in files if f.is_file()})


def _source_corpus() -> list[Path]:
    """Código real de la flota: el mismo corpus de falsos positivos del baseline."""
    files: list[Path] = sorted((ROOT / "packages").rglob("*.py"))
    files.extend(f for f in sorted((ROOT / "scripts").glob("*.py")) if f.name != Path(__file__).name)
    files.extend(sorted((ROOT / "tests").rglob("*.py")))
    for name in CONSUMERS:
        files.extend(sorted((PROJECTS / name / "src").rglob("*.py")))
        files.extend(sorted((PROJECTS / name / "tests").rglob("*.py")))
    return sorted({f for f in files if f.is_file()})


class _FakeClock:
    """Reloj inyectado: nunca duerme de verdad (D4), como en los tests del core."""

    def __init__(self) -> None:
        self._t = 0.0

    def monotonic(self) -> float:
        return self._t

    def sleep(self, seconds: float) -> None:
        self._t += seconds


class _StubProvider:
    """Hoja mínima: completa al instante para medir solo el envoltorio del core."""

    name = "stub"

    def complete(self, request):  # noqa: ANN001 — ProviderRequest, evita import circular aquí
        from llm_client.provider import ProviderResponse

        return ProviderResponse(text="ok", model=request.model)

    def stream(self, request):  # noqa: ANN001
        yield "ok"


# --------------------------------------------------------------------------
# mediciones: cada una devuelve números crudos; el veredicto se deriva después
# --------------------------------------------------------------------------
def m_parser_corpus() -> dict:
    from parser_io import parse

    docs = _corpus()
    secciones = 0
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        secciones = sum(len(parse(p).sections) for p in docs)
        best = min(best, time.perf_counter() - t0)
    return {
        "docs": len(docs),
        "secciones": secciones,
        "segundos": round(best, 4),
        "docs_por_segundo": round(len(docs) / best, 1),
        "piso_docs_por_segundo": PISO_PARSER_DOCS_S,
    }


def m_detect_lines() -> dict:
    from secure_base import detect

    # Misma exclusión declarada del baseline: el archivo que define los patrones
    # contiene literales con forma de teléfono; escanearlo mide el regex, no el código.
    definiciones = ROOT / "packages" / "secure-base" / "src" / "secure_base" / "detectors.py"
    archivos = [f for f in _source_corpus() if f != definiciones]

    lineas_prod = 0
    hallazgos = 0
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        lineas_prod = 0
        hallazgos = 0
        for path in archivos:
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            es_test = "/tests/" in path.as_posix() or path.name.startswith("test_")
            for line in text.splitlines():
                if not es_test:
                    lineas_prod += 1
                hallazgos += len(detect(line))
        best = min(best, time.perf_counter() - t0)
    return {
        "archivos": len(archivos),
        "lineas_produccion": lineas_prod,
        "hallazgos": hallazgos,
        "segundos": round(best, 4),
        "lineas_por_segundo": round(lineas_prod / best, 1),
        "piso_lineas_por_segundo": PISO_DETECT_LINES_S,
    }


def m_validate_text() -> dict:
    from pydantic import BaseModel

    from schema_validate import validate_text

    class _Answer(BaseModel):
        answer: str
        confidence: float

    payload = '{"answer": "42", "confidence": 0.9}'
    ok = 0
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        ok = sum(validate_text(_Answer, payload).ok for _ in range(N_VALIDATE))
        best = min(best, time.perf_counter() - t0)
    return {
        "validaciones": N_VALIDATE,
        "validas": ok,
        "segundos": round(best, 4),
        "validaciones_por_segundo": round(N_VALIDATE / best, 1),
        "piso_validaciones_por_segundo": PISO_VALIDATE_S,
    }


def m_span_construction() -> dict:
    from llm_client import Span

    kw = dict(
        consumer_repo="repo",
        prompt_id="p",
        prompt_version="0.1.0",
        model_alias="big",
        model="big-pickle",
        provider="opencode",
        tokens_input=1,
        tokens_output=1,
        latency_ms=1,
        cost_usd=Decimal("0"),
        retry_count=0,
        status="ok",
    )
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        for i in range(N_SPAN):
            Span(trace_id=f"t{i}", **kw)
        best = min(best, time.perf_counter() - t0)
    return {
        "spans": N_SPAN,
        "segundos": round(best, 4),
        "spans_por_segundo": round(N_SPAN / best, 1),
        "piso_spans_por_segundo": PISO_SPAN_S,
    }


def m_price_key() -> dict:
    from llm_client.pricing import price_key

    modelos = [f"opencode/modelo-{i % 7}" for i in range(N_PRICE_KEY)]
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        for m in modelos:
            price_key(m)
        best = min(best, time.perf_counter() - t0)
    return {
        "lookups": N_PRICE_KEY,
        "segundos": round(best, 4),
        "lookups_por_segundo": round(N_PRICE_KEY / best, 1),
        "piso_lookups_por_segundo": PISO_PRICE_KEY_S,
    }


def m_ratelimiter() -> dict:
    from cache_ratelimit import RateLimiter

    best = float("inf")
    for _ in range(REPS):
        rl = RateLimiter(rpm=60, burst=1_000_000, clock=_FakeClock())
        t0 = time.perf_counter()
        for _ in range(N_RATELIMITER):
            rl.acquire()
        best = min(best, time.perf_counter() - t0)
    return {
        "acquires": N_RATELIMITER,
        "segundos": round(best, 4),
        "acquires_por_segundo": round(N_RATELIMITER / best, 1),
        "piso_acquires_por_segundo": PISO_RATELIMITER_S,
    }


def m_cache_hit_scaling() -> dict:
    from cache_ratelimit import CachedProvider
    from llm_client.provider import ProviderRequest

    # Store grande: CACHE_STORE_GRANDE misses únicos + la clave que se va a leer.
    relleno = [ProviderRequest(model="m", messages=[{"role": "user", "content": str(i)}]) for i in range(CACHE_STORE_GRANDE)]
    hit_req = ProviderRequest(model="m", messages=[{"role": "user", "content": "hit"}])

    grande = CachedProvider(_StubProvider(), ttl_seconds=300.0, clock=_FakeClock())
    for req in relleno:
        grande.complete(req)
    grande.complete(hit_req)
    t0 = time.perf_counter()
    for _ in range(CACHE_HITS):
        grande.complete(hit_req)
    us_grande = (time.perf_counter() - t0) / CACHE_HITS * 1e6

    chico = CachedProvider(_StubProvider(), ttl_seconds=300.0, clock=_FakeClock())
    chico.complete(hit_req)
    t0 = time.perf_counter()
    for _ in range(CACHE_HITS):
        chico.complete(hit_req)
    us_chico = (time.perf_counter() - t0) / CACHE_HITS * 1e6

    return {
        "store_grande": CACHE_STORE_GRANDE,
        "store_chico": 1,
        "hits_medidos": CACHE_HITS,
        "us_por_hit_store_1": round(us_chico, 2),
        "us_por_hit_store_2500": round(us_grande, 2),
        "ratio_coste": round(us_grande / us_chico, 1),
        "umbral_ratio": UMBRAL_RATIO_HIT,
    }


MEDICIONES: list[Callable[[], dict]] = [
    m_parser_corpus,
    m_detect_lines,
    m_validate_text,
    m_span_construction,
    m_price_key,
    m_ratelimiter,
    m_cache_hit_scaling,
]


# --------------------------------------------------------------------------
# veredictos: derivados de la medición, sin cifras escritas a mano
# --------------------------------------------------------------------------
def _veredictos(reporte: dict[str, dict]) -> dict[str, tuple[str, str, str]]:
    def _piso(clave: str, campo: str, piso: str, unidad: str, accion_modulo: str) -> tuple[str, str, str]:
        m = reporte.get(clave, {})
        medido = m.get(campo, 0.0)
        limite = m.get(piso, 1)
        evidencia = (
            f"{medido} {unidad} (piso {limite}); {m.get('segundos', 0)} s de mejor de {REPS}"
        )
        if medido >= limite:
            return "TRUE", evidencia, "—"
        return (
            "FALSE",
            evidencia,
            f"regresión estructural en {accion_modulo}: el piso de METODOLOGIA §7.2 se rompió; revisar el diff reciente del módulo",
        )

    out: dict[str, tuple[str, str, str]] = {
        "parser_corpus": _piso("parser_corpus", "docs_por_segundo", "piso_docs_por_segundo", "docs/s", "parser-io"),
        "detect_lines": _piso("detect_lines", "lineas_por_segundo", "piso_lineas_por_segundo", "líneas/s", "secure-base"),
        "validate_text": _piso("validate_text", "validaciones_por_segundo", "piso_validaciones_por_segundo", "validaciones/s", "schema-validate"),
        "span_construction": _piso("span_construction", "spans_por_segundo", "piso_spans_por_segundo", "spans/s", "llm-client"),
        "price_key": _piso("price_key", "lookups_por_segundo", "piso_lookups_por_segundo", "lookups/s", "llm-client"),
        "ratelimiter": _piso("ratelimiter", "acquires_por_segundo", "piso_acquires_por_segundo", "acquires/s", "cache-ratelimit"),
    }

    ch = reporte.get("cache_hit_scaling", {})
    ratio = ch.get("ratio_coste", 0.0)
    umbral = ch.get("umbral_ratio", 1)
    evidencia = (
        f"{ch.get('us_por_hit_store_1', 0)} µs/hit con store={ch.get('store_chico', '?')} vs "
        f"{ch.get('us_por_hit_store_2500', 0)} µs/hit con store={ch.get('store_grande', '?')} "
        f"(ratio {ratio}×, umbral {umbral}×) sobre {ch.get('hits_medidos', '?')} hits"
    )
    if ratio < umbral:
        out["cache_hit_scaling"] = ("TRUE", evidencia, "—")
    else:
        out["cache_hit_scaling"] = (
            "FALSE",
            evidencia,
            "amortizar la poda del cache (_prune es O(n) por llamada): issue #1 (sem. 15)",
        )
    return out


# --------------------------------------------------------------------------
# informe
# --------------------------------------------------------------------------
def _markdown(reporte: dict[str, dict]) -> str:
    import verification_clauses as vc

    fecha = datetime.now().strftime("%Y-%m-%d")
    veredictos = _veredictos(reporte)
    clausulas = vc.por_clave()
    filas = []
    rotas = []
    for clave, (veredicto, evidencia, accion) in veredictos.items():
        m = reporte.get(clave, {})
        err = m.get("error")
        detalle = f"ERROR DEL INSTRUMENTO: {err}" if err else evidencia
        cl = clausulas.get(clave, {})
        tipo = cl.get("tipo", "SIN ANCLA")
        citas = ", ".join(f"`{c}`" for c in cl.get("citas", [])) or "—"
        filas.append(f"| {clave} | {tipo} | {citas} | {veredicto} | {detalle} | {accion} |")
        if cl.get("problemas"):
            rotas.append(f"- `{clave}`: " + "; ".join(cl["problemas"]))
    cuentas = {k: sum(1 for v in veredictos.values() if v[0] == k) for k in ("TRUE", "FALSE")}

    rotas_md = ""
    if rotas:
        rotas_md = "\n## Anclas rotas\n\n" + "\n".join(rotas) + "\n"

    return f"""# Baseline de rendimiento (METODOLOGIA §7)

Generado por `scripts/verification_perf.py` el {fecha}.
Artefacto de datos: `docs/verification/perf.json` (se escribe en cada ejecución).

La forma es contrato y el número no (§7.1): seis pisos de guardarrail (§7.2) y una
cláusula de forma sobre el hit del cache. Ninguna cifra de este documento está
escrita a mano: todas salen de la ejecución anterior. Un `FALSE` aquí es deuda
publicada (§7.3), no un fallo de la suite.

| medición | tipo de cláusula | ancla | veredicto | evidencia medida | acción |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(filas)}

Totales: {cuentas['TRUE']} `TRUE`, {cuentas['FALSE']} `FALSE`.
{rotas_md}
## Qué NO prueba este baseline

- Corre en una máquina, mejor de {REPS}: es una foto de forma y de órdenes de magnitud,
  no un benchmark de registro ni un percentil de producción.
- Los pisos son relativos al hardware (por eso viven ~100× por debajo): una máquina
  lenta no debe romperlos; una regresión estructural, sí.
- No mide latencia de proveedor, ni redes, ni import de paquete en frío: solo las
  operaciones puras del core que los consumidores llaman en su camino caliente.

## Cómo reproducir

```bash
make verify-perf
```

Equivale a `uv run python scripts/verification_perf.py --markdown`. A diferencia del
baseline de contratos, dos corridas **no** coinciden byte a byte (los tiempos varían):
no hay test de sync exacto, pero `tests/test_verification_perf.py` exige que toda
medición produzca dato, que el informe tenga una fila por cláusula anclada y que los
veredictos salgan de la medición.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Baseline de rendimiento del core (METODOLOGIA §7).")
    ap.add_argument("--markdown", action="store_true", help="escribe PERF.md además del JSON")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "verification" / "perf.json")
    ap.add_argument("--markdown-out", type=Path, default=ROOT / "docs" / "verification" / "PERF.md")
    args = ap.parse_args(argv)

    reporte: dict[str, dict] = {}
    for fn in MEDICIONES:
        try:
            reporte[fn.__name__.removeprefix("m_")] = fn()
        except Exception as exc:  # noqa: BLE001
            reporte[fn.__name__.removeprefix("m_")] = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"· {fn.__name__}", file=sys.stderr)

    payload = {
        "generado_por": "scripts/verification_perf.py",
        "generado_el": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "mediciones": reporte,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    print(f"escrito: {args.out}", file=sys.stderr)

    if args.markdown:
        args.markdown_out.write_text(_markdown(reporte))
        print(f"escrito: {args.markdown_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
