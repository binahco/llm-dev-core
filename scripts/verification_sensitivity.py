"""verification_sensitivity — prueba que el baseline de F0 no es vacuo (F1).

Un oráculo que nunca falla no verifica nada. Para cada cláusula medida en
`scripts/verification_baseline.py` este script inyecta una ruptura deliberada
(monkeypatch en memoria, nunca toca el árbol de trabajo) y exige que el veredicto
de esa medición cambie. Si una ruptura pasa desapercibida, la medición es
decorativa y aquí se reporta como `NO SENSIBLE`.

Uso:
    uv run python scripts/verification_sensitivity.py
    uv run python scripts/verification_sensitivity.py --json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verification_baseline as vb  # noqa: E402


@contextlib.contextmanager
def _roto(modulo: str, atributo: str, sustituto: Any) -> Iterator[None]:
    """Sustituye un atributo de módulo y lo restaura al salir."""
    import importlib

    mod = importlib.import_module(modulo)
    original = getattr(mod, atributo)
    setattr(mod, atributo, sustituto)
    try:
        yield
    finally:
        setattr(mod, atributo, original)


# --------------------------------------------------------------------------
# Rupturas deliberadas: una por cláusula, cada una con su forma de detección
# --------------------------------------------------------------------------
def r_parse_no_determinista() -> dict:
    """Un parse que añade una línea aleatoria debe romper la idempotencia."""
    import itertools

    from parser_io import parse as parse_real

    contador = itertools.count()

    def parse_ruidoso(*a, **k):
        doc = parse_real(*a, **k)
        doc.lines += next(contador)
        return doc

    with _roto("parser_io", "parse", parse_ruidoso):
        m = vb.m_idempotence()
    return {"dato": f"different={m.get('different')}", "detectado": m.get("different", 0) > 0}


def r_rebanada_desplazada() -> dict:
    """Un body desplazado una línea debe romper la fidelidad de rebanada."""
    from parser_io import parse as parse_real

    def parse_desplazado(path, *a, **k):
        doc = parse_real(path, *a, **k)
        for s in doc.sections:
            s.body = "línea inyectada\n" + s.body
        return doc

    with _roto("parser_io", "parse", parse_desplazado):
        m = vb.m_slice_fidelity()
    return {
        "dato": f"sections_lossy={m.get('sections_lossy')}",
        "detectado": m.get("sections_lossy", 0) > 0 and m.get("sections_exact", 1) < m.get("sections", 0),
    }


def r_seccion_vacia_descartada() -> dict:
    """Un parser que vuelve a descartar la sección vacía debe romper la cláusula."""
    from parser_io import parse as parse_real

    def parse_descartador(path, *a, **k):
        doc = parse_real(path, *a, **k)
        doc.sections = [s for s in doc.sections if s.body.strip()]
        return doc

    with _roto("parser_io", "parse", parse_descartador):
        m = vb.m_empty_heading()
    v = vb._veredictos({"empty_heading": m})
    return {
        "dato": f"preservada={m.get('empty_section_preserved')} veredicto={v['empty_heading'][0]}",
        "detectado": m.get("empty_section_preserved") is False and v["empty_heading"][0] == "FALSE",
    }


def r_validador_permisivo() -> dict:
    """Un validador que siempre acepta debe producir desajustes en la enumeración."""
    from llm_client import ValidationResult
    from schema_validate import SchemaRegistry

    original = SchemaRegistry.make_validator

    def validator_permisivo(self, schema_id):
        # el bug: acepta cualquier texto como válido
        return lambda text, schema=None: ValidationResult(ok=True, errors=[], parsed={"ok": True, "count": 0})

    SchemaRegistry.make_validator = validator_permisivo  # type: ignore[method-assign]
    try:
        m = vb.m_schema_enumeration()
    finally:
        SchemaRegistry.make_validator = original  # type: ignore[method-assign]
    return {"dato": f"mismatches={m.get('mismatches')}", "detectado": m.get("mismatches", 0) > 0}


def r_detector_todo_positivo() -> dict:
    """Un detector que marca cualquier línea debe generar hallazgos en producción."""
    import re

    from secure_base import Finding, detect as detect_real

    def detect_furioso(linea: str):
        if re.search(r"[A-Za-z]{3}", linea):
            return [
                Finding(
                    type="github_token",
                    match=linea.strip()[:60],
                    offset=0,
                    length=len(linea.strip()),
                    line=1,
                )
            ]
        return list(detect_real(linea))

    with _roto("secure_base", "detect", detect_furioso):
        m = vb.m_detectors()
    return {"dato": f"findings_production={m.get('findings_production')}", "detectado": m.get("findings_production", 0) > 0}


def r_schedule_siempre_due() -> dict:
    """Un Schedule que siempre dice 'debía' debe romper la recurrencia."""
    import bot_base

    class ScheduleRota:
        def __init__(self, every_seconds=None, *, when=None):
            self.every = every_seconds

        def is_due(self, now_monotonic, last_run_monotonic, now):
            return True

    with _roto("bot_base", "Schedule", ScheduleRota):
        m = vb.m_time_invariants()
    return {
        "dato": f"task_invocations={m.get('task_invocations')} reruns_when_due={m.get('reruns_when_due')}",
        "detectado": m.get("idempotent_same_day") is False or m.get("task_invocations", 0) > 2,
    }


def r_span_sin_cost_usd() -> dict:
    """Un Span al que le falta un campo del ADR debe romper la cláusula.

    El número esperado ya no está hardcodeado: se lee de la lista del ADR-1 §2. La
    ruptura quita `cost_usd`, así que el fallo tiene que aparecer como campo faltante.
    """
    from pydantic import BaseModel

    import llm_client

    class SpanRoto(BaseModel):
        pass

    campos = [f for f in llm_client.Span.model_fields if f != "cost_usd"]
    for nombre in campos:
        SpanRoto.model_fields[nombre] = llm_client.Span.model_fields[nombre]
    SpanRoto.model_rebuild(force=True)

    with _roto("llm_client", "Span", SpanRoto):
        m = vb.m_span_contract()
    v = vb._veredictos({"span_contract": m})
    return {
        "dato": f"en_código={m.get('fields_in_code')} del_adr={m.get('fields_expected_from_adr')} "
        f"faltan={m.get('missing_in_code')} veredicto={v['span_contract'][0]}",
        "detectado": m.get("matches_claim") is False
        and m.get("missing_in_code") == ["cost_usd"]
        and v["span_contract"][0] == "FALSE",
    }


def r_evidencia_con_datos() -> dict:
    """Un modelo fuera de la tabla de precios debe tirar la cláusula de la evidencia.

    Antes la ruptura ponía `calls_column_all_zero=False`, una clave que ya no existe:
    la medición se rescribió en F3 y esta ruptura seguía esperaba un
    veredicto que el código nuevo nunca puede dar.
    """
    m = vb.m_evidence_self_audit()
    falsificado = dict(m)
    falsificado["filas_con_costo_desconocido"] = ["commit-cli", "sec-check"]
    v = vb._veredictos({"evidence_self_audit": falsificado})
    return {
        "dato": f"veredicto={v['evidence_self_audit'][0]} acción={v['evidence_self_audit'][2][:40]!r}",
        "detectado": v["evidence_self_audit"][0] == "FALSE",
    }


def r_cero_sin_procedencia() -> dict:
    """Una página con un $0.0000 sin etiquetar debe detectarse."""
    m = vb.m_evidence_self_audit()
    falsificado = dict(m)
    falsificado["cero_sin_explicacion"] = True
    v = vb._veredictos({"evidence_self_audit": falsificado})
    return {"dato": f"veredicto={v['evidence_self_audit'][0]}", "detectado": v["evidence_self_audit"][0] == "FALSE"}


def r_cifra_verificada() -> dict:
    """Un README con una cifra de contrato que ya no coincide debe dar FALSE.

    Antes esta ruptura fijaba `verificado_por_ejecucion=1` y comprobaba que el
    veredicto dejara de ser FALSE. F3 eliminó esa constante: el criterio ahora es que
    una cifra de contrato contradiga a su oráculo.
    """
    m = vb.m_docs_claims()
    falsificado = dict(m)
    falsificado["claims_falsos"] = [{"repo": "core-smoke", "linea": 72, "cifra": "107", "oraculo": "tests"}]
    v = vb._veredictos({"docs_claims": falsificado})
    return {"dato": f"veredicto={v['docs_claims'][0]}", "detectado": v["docs_claims"][0] == "FALSE"}


# Cada medición de `verification_baseline.MEDICIONES` necesita su ruptura. La clave es
# el nombre de la medición que rompe; `cero_sin_procedencia` es la única extra, una
# segunda forma de fallar la misma cláusula.
RUPTURAS = {
    "idempotence": (r_parse_no_determinista, "parse añade ruido aleatorio"),
    "slice_fidelity": (r_rebanada_desplazada, "body desplazado una línea"),
    "empty_heading": (r_seccion_vacia_descartada, "parser que descarta la sección vacía"),
    "schema_enumeration": (r_validador_permisivo, "validador que siempre acepta"),
    "detectors": (r_detector_todo_positivo, "detector que marca todo"),
    "time_invariants": (r_schedule_siempre_due, "Schedule siempre 'debía'"),
    "span_contract": (r_span_sin_cost_usd, "Span al que le falta cost_usd"),
    "evidence_self_audit": (r_evidencia_con_datos, "modelo fuera de la tabla de precios"),
    "cero_sin_procedencia": (r_cero_sin_procedencia, "$0.0000 sin etiqueta de procedencia"),
    "docs_claims": (r_cifra_verificada, "cifra de contrato que contradice al código"),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sensibilidad del baseline de verificación (F1).")
    ap.add_argument("--json", action="store_true", help="imprime el resultado en JSON")
    args = ap.parse_args(argv)

    filas = []
    insensible = 0
    for clave, (fn, descripcion) in RUPTURAS.items():
        try:
            r = fn()
        except Exception as exc:  # noqa: BLE001
            r = {"dato": f"{type(exc).__name__}: {exc}", "detectado": False}
        if not r["detectado"]:
            insensible += 1
        filas.append({"clause": clave, "break": descripcion, **r})
        print(f"{'detecta ' if r['detectado'] else 'NO VE   '} {clave}: {r['dato']}", file=sys.stderr)

    total = len(filas)
    print(json.dumps({"clausulas": total, "sensibles": total - insensible, "insensibles": insensible, "filas": filas},
                     ensure_ascii=False, indent=2) if args.json else "", file=sys.stderr)
    if args.json:
        print(json.dumps(filas, ensure_ascii=False, indent=2))
    if insensible:
        print(f"FALLO: {insensible} medición(es) no detecta su propia ruptura", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
