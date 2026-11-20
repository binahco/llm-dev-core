"""El baseline y su prueba de sensibilidad son parte del contrato, no notas.

Si `verification_baseline` deja de medir o `verification_sensitivity` deja de detectar
una ruptura, la suite falla: un oráculo vacuo es peor que no tener oráculo.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verification_baseline as vb  # noqa: E402

CLAVES = [
    "slice_fidelity",
    "idempotence",
    "empty_heading",
    "schema_enumeration",
    "detectors",
    "time_invariants",
    "span_contract",
    "evidence_self_audit",
    "docs_claims",
]


def test_toda_medicion_produce_dato() -> None:
    """Ninguna medición puede terminar en error del instrumento."""
    for nombre, fn in zip(CLAVES, vb.MEDICIONES, strict=True):
        resultado = fn()
        assert "error" not in resultado, f"{nombre} falló como instrumento: {resultado.get('error')}"


def test_el_informe_tiene_una_fila_por_clausula_y_ninguna_vacia() -> None:
    """`BASELINE.md` no puede quedar a medio escribir ni con celdas sin evidencia."""
    informe = ROOT / "docs" / "verification" / "BASELINE.md"
    assert informe.is_file(), "falta docs/verification/BASELINE.md: ejecuta `make verify-baseline`"
    filas = [ln for ln in informe.read_text().splitlines() if ln.startswith("| ")]
    cuerpos = [ln for ln in filas if not ln.startswith("| ---") and ln.split("|")[1].strip() != "medición"]
    assert len(cuerpos) == len(CLAVES), f"el informe tiene {len(cuerpos)} filas y se esperaban {len(CLAVES)}"
    for linea in cuerpos:
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        _, tipo, ancla, veredicto, evidencia, accion = celdas
        assert tipo in {"PREEXISTENTE", "DECISION v1.1", "CRITERIO DE PROYECTO"}, linea
        assert ancla, linea
        assert veredicto in {"TRUE", "PARCIAL", "FALSE"}, linea
        assert evidencia and evidencia != "\u2014", linea
        assert accion, linea


def test_cada_clausula_detecta_su_ruptura() -> None:
    """La prueba de sensibilidad debe pasar: ninguna medición es vacua."""
    salida = subprocess.run(
        [sys.executable, str(SCRIPTS / "verification_sensitivity.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert salida.returncode == 0, salida.stderr
    assert "NO VE" not in salida.stderr, salida.stderr


def test_salida_del_baseline_es_json_reproducible() -> None:
    primera = json.loads((ROOT / "docs" / "verification" / "baseline.json").read_text())
    segunda: dict = {}
    for nombre, fn in zip(CLAVES, vb.MEDICIONES, strict=True):
        segunda[nombre] = fn()
    assert set(primera["mediciones"]) == set(CLAVES)
    for clave in CLAVES:
        assert "error" not in primera["mediciones"][clave]
        assert primera["mediciones"][clave] == segunda[clave], f"{clave} no es reproducible"


# --- F2.1: las cláusulas se piden prestadas y su tipo lo decide el tag v1.0.0 ---

import verification_clauses as vc  # noqa: E402


def test_toda_medicion_tiene_clausula_con_ancla() -> None:
    """Ninguna medición puede declarar su propia cláusula: tiene que citarla.

    El registro puede tener más cláusulas que mediciones del baseline (perf,
    METODOLOGIA §7): cada familia de mediciones exige su subconjunto en su test.
    """
    declaradas = {c.clave for c in vc.CLAUSULAS}
    assert set(CLAVES) <= declaradas, "hay mediciones del baseline sin cláusula"


def test_toda_ancla_existe_en_el_archivo_indicado() -> None:
    """Si el ADR se renumera o se reescribe, la suite falla en vez de quedar mudo."""
    rotas = [r for r in vc.resolver_todas() if r["problemas"]]
    assert not rotas, "\n".join(f"{r['clave']}: {p}" for r in rotas for p in r["problemas"])


def test_una_clausula_preexistente_existe_en_el_tag_v1_0_0() -> None:
    """El autor no se declara PREEXISTENTE: lo comprueba `git show v1.0.0`."""
    falsos = [r["clave"] for r in vc.resolver_todas() if r["tipo"] == vc.PREEXISTENTE and not r["anclada_en_v1_0_0"]]
    assert not falsos, f"se declaran preexistentes pero no están en el tag: {falsos}"


def test_las_clausulas_de_v1_1_no_se_presentan_como_preexistentes() -> None:
    """Guarda contra la autoatribución: lo escrito en v1.1 debe figurar como tal."""
    tipos = {r["clave"]: r["tipo"] for r in vc.resolver_todas()}
    assert tipos["slice_fidelity"] == vc.DECISION
    assert tipos["empty_heading"] == vc.DECISION
    assert tipos["detectors"] == vc.DECISION
    for clave in ("span_contract", "schema_enumeration", "idempotence", "time_invariants"):
        assert tipos[clave] == vc.PREEXISTENTE, clave


def test_el_informe_publica_el_tipo_de_cada_clausula() -> None:
    informe = (ROOT / "docs" / "verification" / "BASELINE.md").read_text()
    assert "tipo de cláusula" in informe
    for tipo in (vc.PREEXISTENTE, vc.DECISION, "CRITERIO DE PROYECTO"):
        assert tipo in informe, f"el informe no muestra el tipo {tipo}"


def test_el_informe_declara_la_autorreferencia_de_f0() -> None:
    """El error de F0 queda escrito en el artefacto, no solo en la conversación."""
    informe = (ROOT / "docs" / "verification" / "BASELINE.md").read_text()
    assert "Historial de cláusulas" in informe
    assert "inventé" in informe


class TestF3CifrasVerificables:
    """F3: una cifra de README se verifica contra su oráculo, o no es un claim."""

    def test_ningun_claim_de_contrato_es_falso(self) -> None:
        dc = vb.m_docs_claims()
        assert dc["claims_falsos"] == [], f"cifras falsas en README: {dc['claims_falsos']}"

    def test_se_verifica_al_menos_un_claim_de_camino(self) -> None:
        """Si `contrato` quedara vacía, la medición pasaría sin comprobar nada."""
        dc = vb.m_docs_claims()
        assert dc["claims_de_contrato"] > 0
        assert dc["claims_verificados"] == dc["claims_de_contrato"]

    def test_el_criterio_no_depende_de_una_constante(self) -> None:
        """F3: `verificado_por_ejecucion` era 0 escrito a mano; ahora sale de medir."""
        dc = vb.m_docs_claims()
        assert "verificado_por_ejecucion" not in dc
        assert dc["claims_de_contrato"] == len(dc["claims_falsos"]) + dc["claims_verificados"]

    def test_puertos_y_http_no_cuentan_como_claim(self) -> None:
        """Un puerto o un 429 no afirman nada sobre el comportamiento."""
        assert vb._clasifica_cifra("sirve en localhost:8000", "8000") == "puerto"
        assert vb._clasifica_cifra("| `429` | presupuesto_excedido |", "429") == "http"
        assert vb._clasifica_cifra("Fecha 2026-10-01", "2026") == "fecha"
        assert vb._clasifica_cifra("llega con cost-obs, sem. 39", "39") == "cronologia"

    def test_claim_de_contrato_se_detecta(self) -> None:
        assert vb._clasifica_cifra("span de 20 campos, costo y record/replay", "20") == "contrato"
        assert vb._clasifica_cifra("La suite son sus 134 tests", "134") == "contrato"

    def test_el_claim_de_span_se_contrasta_con_el_codigo(self) -> None:
        """El oráculo de "N campos" es `len(Span.model_fields)`, no una constante."""
        from llm_client import Span

        dc = vb.m_docs_claims()
        assert dc["campos_span_en_codigo"] == len(Span.model_fields)
        spans = [c for c in dc["claims_falsos"] if c["oraculo"] == "len(Span.model_fields)"]
        assert not spans


class TestF3CeroConProcedencia:
    """Un 0 que no dice de dónde viene mezcla costo gratis con dato ausente."""

    def test_cero_de_evidencia_no_se_confunde_con_costo_desconocido(self) -> None:
        ev = vb.m_evidence_self_audit()
        assert ev["filas_con_costo_desconocido"] == []
        assert ev["cero_sin_explicacion"] is False
        assert ev["filas_con_datos_de_llamada"] == ev["filas_totales"]

    def test_la_evidencia_trae_llamadas_de_verdad(self) -> None:
        ev = vb.m_evidence_self_audit()
        assert ev["filas_totales"] == len(vb.CONSUMERS)
        assert ev["calls_cassette"] > 0
        assert ev["tokens_in"] > 0 and ev["tokens_out"] > 0

    def test_precio_de_un_modelo_inventado_no_pasa_gratis(self) -> None:
        from llm_client.pricing import cost_usd, model_price_known

        assert cost_usd("modelo-de-pago-ficticio", 1_000_000, 0) == 0
        assert model_price_known("modelo-de-pago-ficticio") is False
        assert model_price_known("opencode/big-pickle") is True

    def test_la_pagina_no_tiene_ceros_sin_etiqueta(self) -> None:
        html = (ROOT / "docs" / "metrics" / "evidence.html").read_text()
        ceros = html.count("<td>$0.0000")
        con_etiqueta = html.count("$0.0000 <small>(")
        assert ceros == con_etiqueta, f"{ceros - con_etiqueta} celdas de costo sin procedencia"

    def test_la_pagina_publica_tokens_y_separa_span_de_cassette(self) -> None:
        html = (ROOT / "docs" / "metrics" / "evidence.html").read_text()
        assert "llamadas (cassette)" in html and "llamadas (span)" in html
        assert "tokens in/out" in html
        assert "costo desconocido" in html, "la leyenda debe explicar el cuarto estado"
        assert "40 llamadas grabadas en cassettes" in html


def test_cada_ruptura_del_harness_cubre_una_medicion() -> None:
    """Cada medición medida necesita al menos una ruptura que la haga fallar.

    F3 encontró dos casos de lo contrario: `evidence_self_audit` y `docs_claims`
    tenían rupturas que fijaban claves que la medición ya no usaba, así que
    «pasaban» sin comprobar nada.
    """
    import verification_sensitivity as vs

    cubiertas = set(vs.RUPTURAS)
    assert set(CLAVES) <= cubiertas, f"mediciones sin ruptura: {set(CLAVES) - cubiertas}"
    for clave, (fn, _desc) in vs.RUPTURAS.items():
        if clave in CLAVES:
            assert fn()["detectado"], f"la ruptura de {clave} ya no la detecta"
