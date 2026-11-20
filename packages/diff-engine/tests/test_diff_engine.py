"""Tests de diff-engine: determinista, volátiles declarados, hunks con líneas (D4)."""

from __future__ import annotations

import pytest

from diff_engine import VOLATILE_FIELDS, diff_records, diff_text, text_similarity


def test_registros_identicos_son_iguales() -> None:
    reg = {"model": "m", "text": "hola\nmundo", "usage": {"in": 10}}
    report = diff_records(reg, dict(reg))
    assert report.igual
    assert report.similitud_texto == 1.0
    assert report.hunks == []


def test_volatiles_declarados_se_ignoran_y_se_listan() -> None:
    a = {"text": "igual", "timestamp": "1", "span_id": "x", "latency_ms": 5}
    b = {"text": "igual", "timestamp": "2", "span_id": "y", "latency_ms": 999}
    report = diff_records(a, b)
    assert report.igual, "los volátiles no deben romper la igualdad"
    assert sorted(report.volatiles_ignorados) == ["latency_ms", "span_id", "timestamp"]


def test_cambio_de_texto_produce_hunks_y_similitud() -> None:
    a = {"text": "línea uno\nlínea dos\nlínea tres"}
    b = {"text": "línea uno\nlínea DOS\nlínea tres"}
    report = diff_records(a, b)
    assert not report.igual
    assert 0.5 < report.similitud_texto < 1.0
    assert len(report.hunks) == 1
    assert report.hunks[0].op == "cambiada"
    assert report.hunks[0].lineas_a == ["línea dos"]
    assert report.hunks[0].lineas_b == ["línea DOS"]


def test_campo_no_textual_cambia_sin_hunks() -> None:
    a = {"model": "m", "usage": {"in": 1}}
    b = {"model": "m", "usage": {"in": 2}}
    report = diff_records(a, b)
    assert not report.igual
    assert report.hunks == []
    campo = next(c for c in report.campos if c.campo == "usage")
    assert campo.similitud == 0.0


def test_determinismo_dos_llamadas_mismo_resultado() -> None:
    a = {"text": "a\nb\nc", "timestamp": "1"}
    b = {"text": "a\nX\nc", "timestamp": "2"}
    assert diff_records(a, b) == diff_records(a, b)


def test_text_similarity_limites() -> None:
    assert text_similarity("x", "x") == 1.0
    assert text_similarity("x", "y") == 0.0
    assert 0.0 < text_similarity("hola mundo", "hola mundo!") < 1.0


def test_volatiles_por_defecto_cubren_ids_y_tiempos() -> None:
    assert {"timestamp", "span_id", "trace_id", "latency_ms"} <= set(VOLATILE_FIELDS)


def test_diff_text_marcado_agregada_y_eliminada() -> None:
    hunks = diff_text("uno\ndos", "dos\ntres")
    ops = {h.op for h in hunks}
    assert ops == {"agregada", "eliminada"} or ops == {"cambiada"}
