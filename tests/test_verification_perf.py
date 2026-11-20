"""El baseline de rendimiento es parte del contrato, no una nota de benchmark.

A diferencia del baseline de contratos, el JSON de perf no es reproducible byte a byte
(los tiempos cambian entre corridas), así que aquí no hay test de sync exacto: la suite
exige estructura, veredictos derivados de la medición y cláusulas con ancla — igual
que F2.1 exigió para el baseline. Un oráculo vacuo es peor que no tener oráculo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verification_clauses as vc  # noqa: E402
import verification_perf as vp  # noqa: E402

CLAVES = [
    "parser_corpus",
    "detect_lines",
    "validate_text",
    "span_construction",
    "price_key",
    "ratelimiter",
    "cache_hit_scaling",
]


def test_toda_medicion_produce_dato() -> None:
    """Ninguna medición puede terminar en error del instrumento."""
    for nombre, fn in zip(CLAVES, vp.MEDICIONES, strict=True):
        resultado = fn()
        assert "error" not in resultado, f"{nombre} falló como instrumento: {resultado.get('error')}"


def test_los_veredictos_salen_de_la_medicion_no_de_una_constante() -> None:
    """El veredicto de cada piso debe poder voltearse con el número medido."""
    reporte = {clave: fn() for clave, fn in zip(CLAVES, vp.MEDICIONES, strict=True)}
    veredictos = vp._veredictos(reporte)

    # Con la medición fresca, cada piso coincide con comparar medido >= piso.
    for clave in CLAVES[:-1]:
        m = reporte[clave]
        piso = next(v for k, v in m.items() if k.startswith("piso_"))
        medido = next(v for k, v in m.items() if k.endswith("_por_segundo"))
        esperado = "TRUE" if medido >= piso else "FALSE"
        assert veredictos[clave][0] == esperado, clave

    # La cláusula de forma se deriva del ratio medido contra su umbral.
    ch = reporte["cache_hit_scaling"]
    esperado = "TRUE" if ch["ratio_coste"] < ch["umbral_ratio"] else "FALSE"
    assert veredictos["cache_hit_scaling"][0] == esperado


def test_toda_medicion_tiene_clausula_con_ancla() -> None:
    """Las cláusulas de rendimiento viven en METODOLOGIA §7, no en el script."""
    declaradas = {c.clave for c in vc.CLAUSULAS}
    assert set(CLAVES) <= declaradas, "hay mediciones de perf sin cláusula"
    clausulas = vc.por_clave()
    for clave in CLAVES:
        cl = clausulas[clave]
        assert cl["tipo"] == "CRITERIO DE PROYECTO", clave
        assert cl["citas"], f"{clave} sin anclas"
        assert not cl["problemas"], f"{clave}: {cl['problemas']}"


def test_el_informe_tiene_una_fila_por_clausula_y_ninguna_vacia() -> None:
    """`PERF.md` no puede quedar a medio escribir ni con celdas sin evidencia."""
    informe = ROOT / "docs" / "verification" / "PERF.md"
    assert informe.is_file(), "falta docs/verification/PERF.md: ejecuta `make verify-perf`"
    filas = [ln for ln in informe.read_text().splitlines() if ln.startswith("| ")]
    cuerpos = [ln for ln in filas if not ln.startswith("| ---") and ln.split("|")[1].strip() != "medición"]
    assert len(cuerpos) == len(CLAVES), f"el informe tiene {len(cuerpos)} filas y se esperaban {len(CLAVES)}"
    for linea in cuerpos:
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        _, tipo, ancla, veredicto, evidencia, accion = celdas
        assert tipo == "CRITERIO DE PROYECTO", linea
        assert ancla, linea
        assert veredicto in {"TRUE", "FALSE"}, linea
        assert evidencia and evidencia != "\u2014", linea
        assert accion, linea
