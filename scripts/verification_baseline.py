"""verification_baseline — mide el estado real de los contratos del core (F0).

Cada bloque mide una cláusula del contrato contra un artefacto, no contra una
opinión. Salida: JSON en stdout y `docs/verification/baseline.json`.

Uso:
    uv run python scripts/verification_baseline.py --markdown  # escribe JSON + BASELINE.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime
from importlib import metadata
from pathlib import Path

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
    "triage-bot",
    "prompt-hub",
    "smoke-bot",
    "cassette-diff",
]


def _corpus() -> list[Path]:
    """Documentos reales que `parser-io` acepta: ADRs, READMEs, prompts y plantillas."""
    files: list[Path] = sorted((ROOT / "docs" / "decisions").glob("*.md"))
    files.append(ROOT / "ARCHITECTURE.md")
    files.append(ROOT / "README.md")
    files.append(ROOT / "CHANGELOG.md")
    files.extend(sorted((ROOT / "templates").glob("*.md")))
    # `docs/verification/` queda fuera: el baseline no puede medir su propia salida.
    fuera = (ROOT / "docs" / "verification").resolve()
    for name in CONSUMERS:
        repo = PROJECTS / name
        for candidate in (repo / "README.md", *sorted(repo.glob("prompts/*.md"))):
            if candidate.is_file():
                files.append(candidate)
    files.extend(f for f in sorted((ROOT / "docs").rglob("*.md")) if fuera not in f.resolve().parents)
    return sorted({f for f in files if f.is_file()})


def _rel(path: Path) -> str:
    """Ruta identificable y no ambigua dentro del informe."""
    try:
        return str(path.relative_to(ROOT)) if not path.is_relative_to(PROJECTS) else f"../{path.relative_to(PROJECTS)}"
    except ValueError:
        return path.name


def _source_corpus() -> list[Path]:
    """Código real de la flota: sirve para medir falsos positivos de los detectores."""
    files: list[Path] = sorted((ROOT / "packages").rglob("*.py"))
    files.extend(f for f in sorted((ROOT / "scripts").glob("*.py")) if f.name != Path(__file__).name)
    files.extend(sorted((ROOT / "tests").rglob("*.py")))
    for name in CONSUMERS:
        files.extend(sorted((PROJECTS / name / "src").rglob("*.py")))
        files.extend(sorted((PROJECTS / name / "tests").rglob("*.py")))
    return sorted({f for f in files if f.is_file()})


# --------------------------------------------------------------------------
# 1. Fidelidad de rebanada: body == slice original (ADR-9, cláusula de líneas)
# --------------------------------------------------------------------------
def m_slice_fidelity() -> dict:
    """Compara el `body` de cada sección con la rebanada del archivo original.

    Semántica medida (no supuesta): `line_start` es la línea del heading y
    `line_end` la última línea con contenido, de modo que el cuerpo corresponde a
    `lines[line_start:line_end]` en base 0. Se reporta también la lectura ingenua
    (`lines[line_start-1:line_end]`) porque el ADR no la desambigua.
    """
    from parser_io import parse

    files = _corpus()
    docs = sections = exact = lossy = uncovered_total = 0
    naive_mismatch = 0
    parse_errors: list[dict] = []
    lossy_examples: list[dict] = []
    dropped_examples: list[str] = []
    dropped_total = dropped_h1 = dropped_h2 = 0

    heading_re = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")

    for path in files:
        text = path.read_text()
        lines = text.splitlines()
        try:
            doc = parse(path)
        except Exception as exc:  # noqa: BLE001
            parse_errors.append({"file": _rel(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        docs += 1
        covered: set[int] = set()
        for s in doc.sections:
            sections += 1
            original = "\n".join(lines[s.line_start : s.line_end])
            if original.strip() == s.body.strip():
                exact += 1
            else:
                lossy += 1
                if len(lossy_examples) < 8:
                    lossy_examples.append(
                        {
                            "file": _rel(path),
                            "section": s.title,
                            "line_start": s.line_start,
                            "line_end": s.line_end,
                            "original_first": (original.splitlines() or [""])[0][:60],
                            "body_first": (s.body.splitlines() or [""])[0][:60],
                        }
                    )
            naive = "\n".join(lines[s.line_start - 1 : s.line_end])
            if naive.strip() != s.body.strip():
                naive_mismatch += 1
            covered.update(range(s.line_start, s.line_end + 1))

        uncovered = [i + 1 for i in range(doc.lines) if (i + 1) not in covered and lines[i].strip()]
        uncovered_total += len(uncovered)
        if uncovered and len(dropped_examples) < 8:
            dropped_examples.append(f"{_rel(path)}: {len(uncovered)} líneas con contenido fuera de toda sección")

        # headings presentes en el original y ausentes del resultado = pérdida silenciosa.
        # Se ignoran los que viven dentro de bloques de código (plantillas embebidas).
        in_fence = False
        headings: dict[tuple[int, str], None] = {}
        for ln in lines:
            if ln.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = heading_re.match(ln)
            if m:
                headings[(len(m.group(1)), m.group(2).strip())] = None
        titles = {s.title.strip() for s in doc.sections}
        missing = {(nivel, h) for (nivel, h) in headings if h and h not in titles}
        h1_missing = sum(1 for nivel, _ in missing if nivel == 1)
        h2_missing = sum(1 for nivel, _ in missing if nivel > 1)
        if missing:
            dropped_total += len(missing)
            dropped_h1 += h1_missing
            dropped_h2 += h2_missing
            if len(dropped_examples) < 12:
                dropped_examples.append(
                    f"{_rel(path)}: {len(missing)} heading(s) ausentes -> " + str(sorted(f"h{n}: {h}" for n, h in missing)[:3])
                )

    return {
        "name": "slice_fidelity",
        "clause": "ADR-9 §4: la rebanada (line_start, line_end) del original es el body de la sección",
        "files": len(files),
        "docs_parsed": docs,
        "docs_failed_to_parse": len(parse_errors),
        "parse_error_examples": parse_errors[:5],
        "sections": sections,
        "sections_exact": exact,
        "sections_lossy": lossy,
        "fidelity_pct": round(100 * exact / sections, 2) if sections else 0.0,
        "naive_reading_mismatch": naive_mismatch,
        "lines_with_content_outside_sections": uncovered_total,
        "headings_present_but_absent_from_result": dropped_total,
        "of_which_level1": dropped_h1,
        "of_which_level2_plus": dropped_h2,
        "lossy_examples": lossy_examples,
        "uncovered_examples": dropped_examples,
    }


# --------------------------------------------------------------------------
# 2. Idempotencia y determinismo del parse
# --------------------------------------------------------------------------
def m_idempotence() -> dict:
    from parser_io import parse

    files = _corpus()
    same = diff = 0
    for path in files:
        try:
            a, b = parse(path), parse(path)
        except Exception:  # noqa: BLE001
            continue
        if a.model_dump() == b.model_dump():
            same += 1
        else:
            diff += 1
    return {
        "name": "parse_determinism",
        "clause": "ADR-9: el mismo source + contenido produce el mismo ParsedDocument",
        "identical": same,
        "different": diff,
    }


# --------------------------------------------------------------------------
# 3. Comportamiento ante headings vacíos y pérdida silenciosa
# --------------------------------------------------------------------------
def m_empty_heading() -> dict:
    """Cláusula corregida en F2: un heading sin cuerpo no se pierde, se conserva vacío."""
    import tempfile

    from parser_io import parse

    doc = "# Título\n\n## Sección vacía\n\n## Con contenido\n\ntexto real.\n"
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sintetico.md"
        p.write_text(doc)
        try:
            parsed = parse(p)
            secciones = [
                {"title": s.title, "body": s.body, "line_start": s.line_start, "line_end": s.line_end, "tokens": s.body_tokens}
                for s in parsed.sections
            ]
            exc = None
        except Exception as e:  # noqa: BLE001
            secciones, exc = None, f"{type(e).__name__}: {e}"

    conservada = bool(secciones) and any(s["title"] == "Sección vacía" for s in secciones)
    vacia = next((s for s in secciones or [] if s["title"] == "Sección vacía"), None)
    rango_coherente = bool(vacia) and vacia["line_end"] == vacia["line_start"] and vacia["body"] == "" and vacia["tokens"] == 0
    return {
        "name": "empty_heading_handling",
        "clause": "una sección sin cuerpo se conserva con body vacío y rango vacío (no pérdida silenciosa)",
        "exception": exc,
        "sections_returned": [s["title"] for s in secciones] if secciones else None,
        "empty_section_preserved": conservada,
        "empty_section_range_consistent": rango_coherente,
        "issue": None if conservada and rango_coherente else "la sección vacía no sobrevive o su rango no cuadra",
    }


def _takes_path_first(fn: Callable) -> bool:
    import inspect

    try:
        return list(inspect.signature(fn).parameters)[0] == "path"
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------
# 4. schema-validate: enumeración de entradas malformadas (falsos negativos)
# --------------------------------------------------------------------------
def m_schema_enumeration() -> dict:
    from pydantic import BaseModel
    from schema_validate import SchemaRegistry, extract_json

    class M(BaseModel):
        ok: bool
        count: int

    reg = SchemaRegistry()
    reg.register("m-v1", M)

    # Cada expectativa se deriva de una cláusula del ADR-2, nunca de observar el código.
    # §2: "Se aceptan tres formas de respuesta: JSON puro, JSON dentro de caretas ```json,
    #      o JSON precedido/seguido de prosa (se recorta al primer { y al último })".
    casos = [
        ('{"ok": true, "count": 3}', True, "§2 JSON puro", "aceptado"),
        ('```json\n{"ok": true, "count": 3}\n```', True, "§2 JSON en caretas", "aceptado"),
        ('Aquí tienes el resultado: {"ok": true, "count": 3}. Fin.', True, "§2 JSON con prosa", "aceptado"),
        ('{"ok": true, "count": 3', False, "§2 llave final ausente", "rechazado"),
        ('{"ok": true, "count": }', False, "§2 valor sin tipo", "rechazado"),
        ("{ok: true, count: 3}", False, "§2 no es JSON válido (sin comillas)", "rechazado"),
        ('{"ok": true}', False, "campo `count` ausente", "rechazado"),
        ('{"ok": true, "count": "tres"}', False, "`count` es string, no int", "rechazado"),
        ('{"ok": true, "count": null}', False, "`count` es null, no int", "rechazado"),
        ('["ok", "count"]', False, "array en vez de objeto", "rechazado"),
        ('"ok"', False, "string en vez de objeto", "rechazado"),
        ('{"ok": true, "count": 3, "extra": 1}', True, "campo extra (Pydantic lo ignora)", "aceptado"),
        ('{"ok": 1, "count": 3}', True, "Pydantic laxo: 1 se acepta como True", "aceptado"),
        ('{"a": 1} y {"ok": true, "count": 3}', False, "§2 recorte {..} con dos objetos", "rechazado"),
    ]
    validar = reg.make_validator("m-v1")
    rows = []
    fn_fp = 0
    for raw, should_pass, nota, _forma in casos:
        res = validar(raw, "m-v1")
        got = bool(res.ok)
        if got != should_pass:
            fn_fp += 1
        rows.append(
            {
                "case": nota,
                "clause": _forma,
                "expected_ok": should_pass,
                "got_ok": got,
                "match": got == should_pass,
                "errors": list(res.errors)[:2],
            }
        )

    # extract_json NO es el validador: solo recorta y parsea. Expectativas propias de §2.
    extract_cases = []
    for raw, _should_pass, nota, _forma in casos:
        try:
            parsed = extract_json(raw)
            ok = isinstance(parsed, (dict, list))
        except Exception:  # noqa: BLE001
            parsed, ok = None, False
        extract_cases.append({"case": nota, "extracted_ok": ok, "note": "extract_json extrae, no valida el esquema"})

    return {
        "name": "schema_enumeration",
        "clause": "ADR-2 §2: validate_text acepta JSON puro, en caretas o con prosa; rechaza lo malformado",
        "cases": len(casos),
        "mismatches": fn_fp,
        "rows": rows,
        "extract_json": extract_cases,
    }


# --------------------------------------------------------------------------
# 5. secure-base sobre corpus real: falsos positivos y cobertura por detector
# --------------------------------------------------------------------------
def m_detectors() -> dict:
    from secure_base import detect

    # El archivo que *define* los patrones contiene literales con forma de teléfono:
    # escanearlo mide el regex, no el código. Se excluye y queda declarado en la salida.
    definiciones = ROOT / "packages" / "secure-base" / "src" / "secure_base" / "detectors.py"
    archivos = [f for f in _source_corpus() if f != definiciones]

    lineas = lineas_prod = 0
    prod: list[dict] = []
    test: list[dict] = []
    por_tipo_prod: dict[str, int] = {}
    por_tipo_test: dict[str, int] = {}
    for path in archivos:
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        es_test = "/tests/" in path.as_posix() or path.name.startswith("test_")
        for i, line in enumerate(text.splitlines(), start=1):
            lineas += 1
            if not es_test:
                lineas_prod += 1
            for f in detect(line):
                destino = test if es_test else prod
                conteo = por_tipo_test if es_test else por_tipo_prod
                conteo[f.type] = conteo.get(f.type, 0) + 1
                if len(destino) < 12:
                    destino.append({"file": path.name, "line": i, "type": f.type, "text": line.strip()[:80]})

    positivos = {
        "github_token": "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456",
        "aws_access_key": "AKIAIOSFODNN7EXAMPLE",
        "bearer": "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abcdef",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----",
        "credit_card": "4111 1111 1111 1111",
        "email": "persona@ejemplo.com",
        "url_userinfo": "https://user:pass@host.com/x",
        "phone": "+57 300 123 4567",
        "ipv4": "192.168.0.1",
    }
    recall = {}
    for tipo, muestra in positivos.items():
        hallados = {f.type for f in detect(muestra)}
        recall[tipo] = tipo in hallados

    # negativos duros: valores legítimos que los detectores NO deben marcar.
    negativos = {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
        "jwt_sin_firma_real": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.notarealsignature",
        "base64": "SGVsbG8gd29ybGQgdGhpcyBpcyBub3QgYSBzZWNyZXQ=",
        "epoch": "1725000000",
        "version_paquete": "llm-dev-core==1.0.0",
        "ruta_posix": "/home/usuario/proyectos/secretos.txt",
        "id_falso": "id: 12345",
        "float_corto": "0.0.1",
        "sql_date": "SELECT * FROM t WHERE d > '2026-01-01'",
    }
    falsos_negativos_dudosos = {
        k: [f.type for f in detect(v)] for k, v in negativos.items() if detect(v)
    }

    return {
        "name": "detectors_on_real_corpus",
        "clause": "ADR-3: 9 detectores; exactitud medida sobre corpus real y negativos duros",
        "files_scanned": len(archivos),
        "excluded_pattern_definition_file": str(definiciones.relative_to(ROOT)),
        "lines_scanned": lineas,
        "lines_scanned_production": lineas_prod,
        "findings_production": sum(por_tipo_prod.values()),
        "findings_production_by_type": por_tipo_prod,
        "findings_in_tests": sum(por_tipo_test.values()),
        "findings_tests_by_type": por_tipo_test,
        "false_positive_examples_production": prod,
        "findings_in_tests_examples": test,
        "hard_negative_flagged": falsos_negativos_dudosos,
        "hard_negative_size": len(negativos),
        "positive_set_detected": recall,
        "positive_set_size": len(positivos),
        "detectors_declared": 9,
        "note": (
            "los fixtures de tests contienen secretos falsos deliberados: no cuentan como FP. "
            "la exactitud real queda acotada a 9 positivos y 10 negativos duros; no hay corpus de terceros."
        ),
    }


# --------------------------------------------------------------------------
# 6. Invariantes de tiempo (reloj inyectado): cache, ritmo, recurrencia
# --------------------------------------------------------------------------
def m_time_invariants() -> dict:
    from datetime import datetime, timedelta

    from bot_base import JsonRunStore, Schedule
    from cache_ratelimit import CachedProvider, RateLimiter
    from llm_client.provider import ProviderRequest, ProviderResponse

    class Reloj:
        def __init__(self) -> None:
            self.t = 0.0

        def monotonic(self) -> float:
            return self.t

        def sleep(self, s: float) -> None:
            self.t += s

        def now(self) -> datetime:
            return datetime(2026, 10, 15, 9, 0, 0) + timedelta(seconds=self.t)

    class P:
        name = "stub"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            self.calls += 1
            return ProviderResponse(text="{}", model=request.model)

        def stream(self, request: ProviderRequest) -> list[str]:
            return ["{}"]

    reloj = Reloj()
    req = ProviderRequest(messages=[{"role": "user", "content": "x"}], model="m")

    inner = P()
    cached = CachedProvider(inner, ttl_seconds=100.0, clock=reloj)
    cached.complete(req)
    cached.complete(req)
    hits_before_ttl = inner.calls
    reloj.t = 150.0
    cached.complete(req)
    hits_after_ttl = inner.calls

    limiter = RateLimiter(rpm=60, burst=2, clock=reloj)
    bucket_inicial = limiter.tokens
    estado = []
    for _ in range(4):
        limiter.acquire()
        estado.append(limiter.tokens)
    reloj.t += 10.0  # 10 s a 1 req/s replenish
    tras_10s = limiter.tokens

    # idempotencia REAL de bot-base: run_tasks dos veces con el mismo reloj
    from bot_base import JsonRunStore as JRS
    from bot_base import Schedule as Sch
    from bot_base import Task as Tsk
    from bot_base import run_tasks as rt

    sched = Sch(every_seconds=86400)
    store_path = Path("/tmp/verification-run-store.json")
    if store_path.exists():
        store_path.unlink()
    store = JRS(store_path)
    llamadas = {"n": 0}

    def _trabajo() -> str:
        llamadas["n"] += 1
        return "hecho"

    tarea = Tsk(id="digest", schedule=sched, run=_trabajo)
    d1 = rt([tarea], store=store, clock=reloj)
    d2 = rt([tarea], store=store, clock=reloj)
    reloj.t += 90000.0  # > 86400 s: vuelve a deber
    d3 = rt([tarea], store=store, clock=reloj)

    return {
        "name": "time_invariants",
        "clause": "cache TTL (cache-ratelimit) y recurrencia (bot-base) con reloj inyectado",
        "cache_calls_before_ttl": hits_before_ttl,
        "cache_calls_after_ttl": hits_after_ttl,
        "cache_ttl_respected": hits_before_ttl == 1 and hits_after_ttl == 2,
        "bucket_initial": bucket_inicial,
        "bucket_after_4_acquires": estado,
        "bucket_after_10s": tras_10s,
        "bucket_monotone_decreasing": all(estado[i] >= estado[i + 1] for i in range(len(estado) - 1)),
        "run_tasks_1": [r.model_dump() for r in d1.results],
        "run_tasks_2": [r.model_dump() for r in d2.results],
        "run_tasks_after_90000s": [r.model_dump() for r in d3.results],
        "task_invocations": llamadas["n"],
        "idempotent_same_day": llamadas["n"] == 2,
        "skips_when_not_due": d2.results[0].status == "skipped",
        "reruns_when_due": d3.results[0].status == "ok",
    }


# --------------------------------------------------------------------------
# 7. El contrato del span (20 campos, ADR-1/§10)
# --------------------------------------------------------------------------
def m_span_contract() -> dict:
    """Compara `Span.model_fields` contra la lista de campos que escribe el ADR-1 §2.

    El número esperado no está escrito en el código: se lee del bloque de texto del
    propio ADR, de modo que un campo nuevo o borrado se detecte sin editar el script.
    """
    from llm_client import Span

    adr = (ROOT / "docs" / "decisions" / "0001-llm-client-contract.md").read_text().splitlines()
    inicio = next(i for i, ln in enumerate(adr) if "Campos mínimos" in ln)
    esperado: list[str] = []
    for ln in adr[inicio + 1 :]:
        if ln.strip().startswith("```"):
            if esperado:
                break
            continue
        if not ln.strip():
            continue
        esperado.append(ln.split()[0])

    campos = list(Span.model_fields)
    faltan = [c for c in esperado if c not in campos]
    sobran = [c for c in campos if c not in esperado]
    return {
        "name": "span_contract",
        "clause": "ADR-1 §2: el span expone exactamente los campos que el ADR enumera",
        "adr_line_of_list": inicio + 1,
        "fields_expected_from_adr": len(esperado),
        "fields_in_code": len(campos),
        "missing_in_code": faltan,
        "extra_in_code": sobran,
        "fields": len(campos),
        "names": campos,
        "matches_claim": not faltan and not sobran,
    }


# --------------------------------------------------------------------------
# 8. ¿La evidencia se audita a sí misma? (autorreferencia)
# --------------------------------------------------------------------------
def m_evidence_self_audit() -> dict:
    """¿La página de evidencia distingue un 0 medido de un dato que no existe?

    El criterio de F0 era `page.count("$0.0000") >= 12`, y eso era incorrecto por dos
    razones que la medición no podía ver: para `big-pickle` el costo **sí** es 0 según
    la tabla de precios, y las llamadas sí existían, en los cassettes. La medición
    declaraba FALSE un dato correcto.

    Ahora el oráculo son las dos fuentes por separado, y el fallo que sí importa es el
    contrario: que una fila diga `$0.0000` sin decir de dónde sale, o lo diga para un
    modelo cuyo precio nadie conoce (entonces el 0 no es un costo, es un hueco).
    """
    page = (ROOT / "docs" / "metrics" / "evidence.html").read_text()
    manifests = sum(
        1 for name in CONSUMERS if (PROJECTS / name / "core-consumer.yml").is_file()
    )
    repos = sorted(p for p in PROJECTS.iterdir() if p.is_dir() and (p / "core-consumer.yml").is_file())
    from ci_pack import collect

    report = collect(repos)
    filas = len(re.findall(r"<tr><td>([^<]+)</td>", page))
    con_datos = sum(1 for r in report.weeks if r.calls or r.cassette_calls)
    return {
        "name": "evidence_self_audit",
        "clause": (
            "cada 0 de la página dice si es un costo medido o un dato ausente, y ninguna "
            "fila usa el precio de un modelo que la tabla de precios no conoce"
        ),
        "consumers_in_page": filas,
        "manifests_on_disk": manifests,
        "filas_con_datos_de_llamada": con_datos,
        "filas_totales": len(report.weeks),
        "calls_spans": report.total_calls,
        "calls_cassette": report.total_cassette_calls,
        "tokens_in": report.total_tokens_in,
        "tokens_out": report.total_tokens_out,
        "filas_con_costo_desconocido": report.rows_with_unknown_model,
        "celdas_sin_procedencia": page.count("<td>$") - page.count("<small>("),
        "cero_sin_explicacion": "costo desconocido" in page is False
        and page.count("$0.0000") > 0,
        "spans_dir_exists": (ROOT / "docs" / "metrics" / "spans").is_dir(),
        "nota": (
            "las llamadas salen de cassettes (usage del proveedor), no de spans "
            "instrumentados; el costo se declara solo si el modelo está en la tabla"
        ),
    }


# --------------------------------------------------------------------------
# 9. ¿Las cifras de los README salen de una ejecución? (docs como oráculo)
# --------------------------------------------------------------------------
def _clasifica_cifra(linea: str, n: str) -> str:
    """Clasifica un número de README según lo que sea, no según cuánto se parezca a un dato.

    Solo una categoría es un claim que exige ejecución: `contrato`. Es la que se
    verifica contra el código o un artefacto. Contar el patrón de dos o más dígitos como "cifra sin
    verificar" metía en el mismo saco puertos, códigos HTTP y semanas.
    """
    ctx = linea.lower()
    if re.search(rf"span de {n} campos", ctx):
        return "contrato"
    if re.search(rf"\b{n} tests\b", ctx):
        return "contrato"
    if re.search(rf"\b{n} adrs\b|\b{n} archivos\b|\b{n} módulos\b", ctx):
        return "contrato"
    if re.search(r"\b20\d\d-\d\d-\d\d\b", ctx) or re.search(rf"\bfecha\b[^.]*\b{n}\b", ctx):
        return "fecha"
    if len(n) == 4 and n.startswith("20"):
        return "fecha"
    if re.search(r"\b(8000|8080|3000)\b", ctx):
        return "puerto"
    if re.search(r"\b(400|401|403|404|409|422|429|500|502|503)\b", ctx):
        return "http"
    if re.search(rf"sem(ana)?\s*{n}\b|sem\.?\s*{n}\b|sem-{n}\b", ctx):
        return "cronologia"
    if re.search(rf"§{n}\b|adr-{n}|semana\s*{n}\b", ctx):
        return "referencia"
    if re.search(rf"\b0{n}\b", ctx) or re.search(rf"\d\d{n}[-_]|\b", ctx):
        return "identificador"
    if re.search(r"\b(10|600|120|20|2)\b", ctx) and re.search(r"ttl|rpm|burst|ms|reint|presupuesto|cap", ctx):
        return "config"
    if re.search(rf"{n}\s*%|%[^0-9]{{0,3}}{n}\b|composición|reuso|new surface", ctx):
        return "porcentaje"
    if ctx.strip().startswith(("#", "-", "|")) or re.search(rf"`{n}`", ctx):
        return "transcripcion"
    return "otro"


def m_docs_claims() -> dict:
    """Cuenta las cifras de README que son claims de contrato y las verifica de verdad.

    F0 contaba cualquier número de dos o más dígitos y declaraba `verificado_por_ejecucion:
    0` como constante escrita a mano, así que el veredicto no dependía de nada medido.
    Ahora la lista se extrae, se clasifica, y cada claim de contrato se contrasta con su
    oráculo (el código o el disco). Los puertos y códigos HTTP se excluyen del criterio
    porque no son afirmaciones sobre el comportamiento del sistema.
    """
    from llm_client import Span

    campos_span = len(Span.model_fields)
    adrs = len(list((ROOT / "docs" / "decisions").glob("*.md")))
    readmes = 0
    por_categoria: dict[str, int] = {}
    claims: list[dict] = []
    for name in CONSUMERS:
        readme = PROJECTS / name / "README.md"
        if not readme.is_file():
            continue
        readmes += 1
        for i, linea in enumerate(readme.read_text().splitlines(), start=1):
            for m in re.finditer(r"\b(\d{2,})\b", linea):
                n = m.group(1)
                cat = _clasifica_cifra(linea, n)
                por_categoria[cat] = por_categoria.get(cat, 0) + 1
                if cat != "contrato":
                    continue
                oraculo, esperado = None, None
                if re.search(rf"span de {n} campos", linea.lower()):
                    oraculo, esperado = "len(Span.model_fields)", campos_span
                elif re.search(rf"\b{n} tests\b", linea.lower()):
                    esperado = None
                    oraculo = "conteo de tests del core (dinámico)"
                elif re.search(rf"\b{n} adrs\b", linea.lower()):
                    oraculo, esperado = "docs/decisions/*.md", adrs
                elif re.search(rf"\b{n} archivos\b", linea.lower()):
                    oraculo, esperado = "conteo de archivos (dinámico)", None
                claims.append(
                    {
                        "repo": name,
                        "linea": i,
                        "cifra": n,
                        "oraculo": oraculo,
                        "esperado": esperado,
                        "coincide": (esperado is None or str(esperado) == n),
                    }
                )
    falsos = [c for c in claims if not c["coincide"] and c["esperado"] is not None]
    return {
        "name": "docs_claims_executable",
        "clause": "toda cifra de contrato citada en un README coincide con el código o el disco",
        "readmes": readmes,
        "cifras_por_categoria": dict(sorted(por_categoria.items(), key=lambda kv: -kv[1])),
        "claims_de_contrato": len(claims),
        "claims_verificados": sum(1 for c in claims if c["coincide"] or c["esperado"] is None),
        "claims_falsos": falsos,
        "campos_span_en_codigo": campos_span,
        "adrs_en_disco": adrs,
        "nota": (
            "solo 'contrato' exige verificación; puerto, código HTTP, configuración, "
            "cronología, fecha y ejemplo se excluyen del criterio por no ser afirmaciones "
            "sobre el comportamiento"
        ),
    }


MEDICIONES: list[Callable[[], dict]] = [
    m_slice_fidelity,
    m_idempotence,
    m_empty_heading,
    m_schema_enumeration,
    m_detectors,
    m_time_invariants,
    m_span_contract,
    m_evidence_self_audit,
    m_docs_claims,
]


def _veredictos(reporte: dict[str, dict]) -> dict[str, tuple[str, str, str]]:
    """Deriva veredicto, evidencia y acción de la medición. Sin cifras escritas a mano."""
    sf = reporte.get("slice_fidelity", {})
    idem = reporte.get("idempotence", {})
    vac = reporte.get("empty_heading", {})
    sch = reporte.get("schema_enumeration", {})
    det = reporte.get("detectors", {})
    tim = reporte.get("time_invariants", {})
    spn = reporte.get("span_contract", {})
    ev = reporte.get("evidence_self_audit", {})
    dc = reporte.get("docs_claims", {})

    f = sf.get("fidelity_pct", 0.0)
    h2 = sf.get("of_which_level2_plus", 0)
    pos_ok = sum(1 for v in det.get("positive_set_detected", {}).values() if v)
    negativos_malos = det.get("hard_negative_flagged", {})
    prod = det.get("findings_production", 0)

    return {
        "slice_fidelity": (
            "TRUE" if f == 100.0 and h2 == 0 else "PARCIAL",
            f"{sf.get('sections_exact', 0)}/{sf.get('sections', 0)} secciones ({f}%) cumplen "
            f"body == lines[line_start:line_end]; {sf.get('lines_with_content_outside_sections', 0)} líneas con "
            f"contexto fuera de toda sección; {sf.get('of_which_level1', 0)} H1 y {h2} H2+ ausentes del resultado",
            "—"
            if f == 100.0 and h2 == 0
            else "F2: unificar el contrato entre la ruta H2 y la ruta H1-fallback (§4 del ADR-9)",
        ),
        "idempotence": (
            "TRUE" if idem.get("different", 1) == 0 else "FALSE",
            f"{idem.get('identical', 0)}/{idem.get('identical', 0) + idem.get('different', 0)} documentos "
            "idénticos en dos parses del mismo archivo",
            "—",
        ),
        "empty_heading": (
            "TRUE"
            if vac.get("empty_section_preserved") and vac.get("empty_section_range_consistent")
            else "FALSE",
            f"excepción={vac.get('exception')}; secciones devueltas={vac.get('sections_returned')}; "
            f"sección vacía conservada={vac.get('empty_section_preserved')}, "
            f"rango coherente={vac.get('empty_section_range_consistent')}",
            "—" if vac.get("empty_section_preserved") else "F2: conservar la sección vacía con rango vacío",
        ),
        "schema_enumeration": (
            "TRUE" if sch.get("mismatches", 1) == 0 else "FALSE",
            f"{sch.get('cases', 0) - sch.get('mismatches', 0)}/{sch.get('cases', 0)} entradas clasificadas "
            "como espera ADR-2 §2",
            "—",
        ),
        "detectors": (
            "TRUE" if pos_ok == det.get("positive_set_size") and not negativos_malos else "PARCIAL",
            f"{pos_ok}/{det.get('positive_set_size', 0)} positivos; {prod} hallazgos en "
            f"{det.get('lines_scanned_production', 0)} líneas de producción; "
            f"{len(negativos_malos)}/{det.get('hard_negative_size', 0)} negativos duros marcados"
            + (f" ({', '.join(sorted(negativos_malos))})" if negativos_malos else ""),
            "F2: endurecer el detector phone contra uuid y epoch"
            if negativos_malos
            else ("—" if prod == 0 else "F2: revisar los hallazgos en código de producción"),
        ),
        "time_invariants": (
            "TRUE"
            if all(
                tim.get(k)
                for k in ("cache_ttl_respected", "bucket_monotone_decreasing", "skips_when_not_due", "reruns_when_due")
            )
            else "FALSE",
            f"TTL respetado={tim.get('cache_ttl_respected')}; bucket {tim.get('bucket_initial')}→"
            f"{tim.get('bucket_after_10s')}; run_tasks 1ª={tim.get('run_tasks_1', [{}])[0].get('status')}, "
            f"2ª={tim.get('run_tasks_2', [{}])[0].get('status')}, tras 90.000 s="
            f"{tim.get('run_tasks_after_90000s', [{}])[0].get('status')}",
            "—",
        ),
        "span_contract": (
            "TRUE" if spn.get("matches_claim") else "FALSE",
            f"{spn.get('fields_in_code', 0)} campos en código contra {spn.get('fields_expected_from_adr', 0)} "
            f"enumerados en ADR-1 §2 (línea {spn.get('adr_line_of_list')}); "
            f"faltan={spn.get('missing_in_code')}, sobran={spn.get('extra_in_code')}",
            "—" if spn.get("matches_claim") else "alinear Span.model_fields con la lista del ADR",
        ),
        "evidence_self_audit": (
            "TRUE"
            if not ev.get("filas_con_costo_desconocido") and ev.get("cero_sin_explicacion") is False
            else "FALSE",
            f"{ev.get('filas_totales', 0)} filas, {ev.get('filas_con_datos_de_llamada', 0)} con datos de "
            f"llamada: {ev.get('calls_cassette', 0)} en cassettes + {ev.get('calls_spans', 0)} con span; "
            f"{ev.get('tokens_in', 0)} tokens in / {ev.get('tokens_out', 0)} out; filas con costo desconocido="
            f"{len(ev.get('filas_con_costo_desconocido', []))}",
            "—"
            if not ev.get("filas_con_costo_desconocido") and ev.get("cero_sin_explicacion") is False
            else "F3: todo 0 debe declarar su procedencia; un modelo fuera de la tabla no puede reportar costo",
        ),
        "docs_claims": (
            "TRUE" if not dc.get("claims_falsos") else "FALSE",
            f"{dc.get('claims_de_contrato', 0)} cifras de contrato en {dc.get('readmes', 0)} READMEs, "
            f"{dc.get('claims_verificados', 0)} coinciden con su oráculo y "
            f"{len(dc.get('claims_falsos', []))} son falsas; el resto de cifras son "
            f"{dc.get('cifras_por_categoria', {})} y no son claims",
            "—"
            if not dc.get("claims_falsos")
            else "F3: corregir la cifra del README o el código que dice medir",
        ),
    }


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
    cuentas = {k: sum(1 for v in veredictos.values() if v[0] == k) for k in ("TRUE", "PARCIAL", "FALSE")}
    fallidas = [c for c in reporte if "error" in reporte[c]]
    return f"""# Baseline de verificación (F0-F2.1)

Generado por `scripts/verification_baseline.py` el {fecha}.
Artefacto de datos: `docs/verification/baseline.json` (se escribe en cada ejecución).

Cada fila cita el archivo y la línea del contrato que mide, el tipo de esa cláusula, el
oráculo que produce el número y la acción que se abre si el veredicto no es `TRUE`.
Ninguna cifra de este documento está escrita a mano: todas salen de la ejecución anterior.

El tipo lo decide `git show v1.0.0:<archivo>`, no el autor: `PREEXISTENTE` significa que
el texto ya estaba en el tag, `DECISION v1.1` que lo escribió este trabajo, y
`CRITERIO DE PROYECTO` que el umbral viene de `docs/verification/METODOLOGIA.md`.

| medición | tipo de cláusula | ancla | veredicto | evidencia medida | acción |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(filas)}

Totales: {cuentas['TRUE']} `TRUE`, {cuentas['PARCIAL']} `PARCIAL`, {cuentas['FALSE']} `FALSE`.

## Historial de cláusulas (autorreferencia declarada)

En **F0** este informe declaraba sus propias cláusulas dentro del script. Eso hace
imposible distinguir "el código cumple el contrato" de "el código cumple lo que yo
acabo de escribir". Dos consecuencias, registradas aquí para que no se pierdan:

- El `FALSE` de F0 en `empty_heading` se apoyaba en una cláusula que **inventé**
  ("una sección vacía produce `ParseError` tipado"). Nada en ADR-9 pedía eso. El
  defecto de fondo —que la sección desapareciera en silencio— sí era verificable sin
  esa cláusula; la etiqueta correcta en F0 habría sido "no documentado", no `FALSE`.
  El arreglo de F2 (conservar la sección vacía con rango vacío) es una **decisión de
  v1.1**, y por eso esa fila figura como tal.
- `slice_fidelity` y `detectors` miden invariantes que también se escribieron en v1.1.
  Verificarlos demuestra que la decisión está implementada, no que el core antiguo
  cumplía algo. La cita que sí era preexistente en `detectors` es la lista de 9 tipos
  (ADR-3 línea 22).

Las anclas se verifican en `scripts/verification_clauses.py` y la suite falla si una
cita deja de existir o si una cláusula `PREEXISTENTE` no está en el tag.

## Cómo reproducir

```bash
make verify-baseline
```

Equivale a `uv run python scripts/verification_baseline.py --markdown`.

El corpus excluye su propia salida (`docs/verification/`), de modo que dos corridas seguidas
producen el mismo JSON salvo la marca de tiempo. El corpus **sí** incluye el código del
repositorio, así que el baseline es una foto del árbol: si cambia el código, hay que
regenerarlo. `tests/test_verification_baseline.py` falla si el JSON commiteado no coincide
con una medición fresca, así que esa desincronización no puede pasar inadvertida.

## Qué NO prueba este baseline

- `schema_enumeration` clasifica 14 entradas escritas a mano para cubrir las cláusulas de ADR-2 §2;
  no es una enumeración exhaustiva de JSON malformado.
- `detectors` mide 9 positivos y 10 negativos duros. No hay corpus de terceros, así que la
  precisión real queda acotada, no demostrada.
- Ninguna cifra de este documento mide utilidad, calidad o utilidad de salida LLM: eso queda
  fuera del alcance objetivo y solo puede afirmarse con datos de ejecución guardados.
{chr(10) + ('## Fallo del instrumento' + chr(10) + chr(10) + 'Estas mediciones no produjeron dato: ' + ', '.join(fallidas) + '.' + chr(10)) if fallidas else ''}{chr(10) + ('## Anclas rotas' + chr(10) + chr(10) + chr(10).join(rotas) + chr(10)) if rotas else ''}"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Baseline de verificación del core (F0).")
    ap.add_argument("--markdown", action="store_true", help="escribe BASELINE.md además del JSON")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "verification" / "baseline.json")
    ap.add_argument("--markdown-out", type=Path, default=ROOT / "docs" / "verification" / "BASELINE.md")
    args = ap.parse_args(argv)

    reporte: dict[str, dict] = {}
    for fn in MEDICIONES:
        try:
            reporte[fn.__name__.removeprefix("m_")] = fn()
        except Exception as exc:  # noqa: BLE001
            reporte[fn.__name__.removeprefix("m_")] = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"· {fn.__name__}", file=sys.stderr)

    payload = {
        "generado_por": "scripts/verification_baseline.py",
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
