"""verification_clauses — anclas verificables de cada cláusula medida en F0.

Problema que resuelve: en F0 el propio instrumento declaraba sus cláusulas, así que
un `TRUE` podía significar "el código cumple lo que yo escribí". En F2.1 la cláusula
se pide prestada a un archivo y el harness decide su tipo contra un artefacto
independiente: el tag `v1.0.0`.

- Si el texto literal existía en `git show v1.0.0:<archivo>`, es `PREEXISTENTE`:
  el contrato era de antes de este trabajo.
- Si no existía, es `DECISION v1.1`: la escribió este trabajo y por tanto no puede
  presentarse como verificación de nada anterior.

Nada depende de que el autor se auto-declare `PREEXISTENTE`: el tag decide.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PREEXISTENTE = "PREEXISTENTE"
DECISION = "DECISION v1.1"
PROYECTO = "CRITERIO DE PROYECTO"
TAG = "v1.0.0"


@dataclass(frozen=True)
class Ancla:
    """Una cita literal del contrato, con el archivo y la línea donde vive."""

    archivo: str
    linea: int
    texto: str
    seccion: str = ""

    def ruta(self) -> Path:
        return ROOT / self.archivo


@dataclass(frozen=True)
class Clausula:
    clave: str
    resumen: str
    anclas: tuple[Ancla, ...]
    tipo_forzado: str | None = None
    nota: str = ""


CLAUSULAS: tuple[Clausula, ...] = (
    Clausula(
        clave="span_contract",
        resumen="El span expone exactamente los campos que el ADR enumera.",
        anclas=(Ancla("docs/decisions/0001-llm-client-contract.md", 58, "Campos mínimos"),),
        nota="el número de campos sale de la lista del ADR, no de una constante",
    ),
    Clausula(
        clave="schema_enumeration",
        resumen="validate_text acepta las tres formas de respuesta y rechaza lo malformado.",
        anclas=(Ancla("docs/decisions/0002-schema-validate-contract.md", 37, "Se aceptan tres formas de respuesta"),),
    ),
    Clausula(
        clave="idempotence",
        resumen="El mismo source + contenido produce el mismo ParsedDocument.",
        anclas=(Ancla("docs/decisions/0009-parser-io-contract.md", 50, "Determinismo (D4)"),),
    ),
    Clausula(
        clave="time_invariants",
        resumen="TTL por entrada, ráfaga limitada y tareas que no se repiten antes de su periodo.",
        anclas=(
            Ancla("docs/decisions/0007-cache-ratelimit-contract.md", 21, "ráfaga 12"),
            Ancla("docs/decisions/0007-cache-ratelimit-contract.md", 50, "Poda por expiración"),
            Ancla("docs/decisions/0008-bot-base-contract.md", 72, "respeta idempotencia"),
        ),
    ),
    Clausula(
        clave="slice_fidelity",
        resumen="body es exactamente la rebanada (line_start, line_end) del archivo.",
        anclas=(Ancla("docs/decisions/0009-parser-io-contract.md", 58, "Contrato de líneas"),),
        nota="el invariante literal lo escribió este trabajo en v1.1; en v1.0 el ADR solo decía «mapeo a línea»",
    ),
    Clausula(
        clave="empty_heading",
        resumen="Un heading sin cuerpo sobrevive con body vacío y rango vacío.",
        anclas=(Ancla("docs/decisions/0009-parser-io-contract.md", 67, "Un heading sin cuerpo no es ruido"),),
        nota="en v1.0 la sección vacía se descartaba en silencio y el ADR no lo decía en ningún lado",
    ),
    Clausula(
        clave="detectors",
        resumen="Nueve tipos de hallazgo; `phone` exige forma escrita.",
        anclas=(
            Ancla("docs/decisions/0003-secure-base-contract.md", 22, "aws_access_key"),
            Ancla("docs/decisions/0003-secure-base-contract.md", 37, "exige forma escrita"),
        ),
        nota="la lista de 9 tipos es preexistente; el umbral de precisión de phone es decisión de v1.1",
    ),
    Clausula(
        clave="evidence_self_audit",
        resumen="Todo cero de la página de evidencia declara si es costo medido o dato ausente.",
        anclas=(
            Ancla("docs/verification/METODOLOGIA.md", 52, "Un cero que no dice de dónde viene no es un dato"),
            Ancla("docs/decisions/0006-ci-pack-contract.md", 47, "Un cero declara su procedencia"),
        ),
        tipo_forzado=PROYECTO,
        nota=(
            "el umbral no venía de un ADR: es la exigencia acordada para este trabajo. "
            "El criterio de F0 (buscar $0.0000 en la página) declaraba FALSE un dato "
            "correcto, porque para big-pickle el costo 0 sí está medido"
        ),
    ),
    Clausula(
        clave="docs_claims",
        resumen="Toda cifra de contrato citada en un README coincide con el código o el disco.",
        anclas=(
            Ancla("docs/verification/METODOLOGIA.md", 29, "Cifra verificable"),
            Ancla("docs/verification/METODOLOGIA.md", 35, "No toda cifra es un"),
        ),
        tipo_forzado=PROYECTO,
        nota=(
            "F0 contaba cualquier número de dos o más dígitos y fijaba "
            "verificado_por_ejecucion=0 como constante, así que el veredicto no dependía "
            "de nada medido; F3 clasifica la cifra antes de exigirle una ejecución"
        ),
    ),
    # --- rendimiento (METODOLOGIA §7): pisos y forma -----------------------
    Clausula(
        clave="parser_corpus",
        resumen="parser-io recorre el corpus de documentos a un ritmo que no colapsó.",
        anclas=(Ancla("docs/verification/METODOLOGIA.md", 106, "Pisos de guardarrail"),),
        tipo_forzado=PROYECTO,
        nota="piso a ~1/100 de lo medido: solo una regresión estructural lo rompe",
    ),
    Clausula(
        clave="detect_lines",
        resumen="secure-base escanea el código de la flota línea a línea sin colapsar.",
        anclas=(Ancla("docs/verification/METODOLOGIA.md", 106, "Pisos de guardarrail"),),
        tipo_forzado=PROYECTO,
        nota="piso a ~1/100 de lo medido; mismo corpus y exclusión de detectors.py que el baseline",
    ),
    Clausula(
        clave="validate_text",
        resumen="schema-validate valida una respuesta extraída sin colapsar.",
        anclas=(Ancla("docs/verification/METODOLOGIA.md", 106, "Pisos de guardarrail"),),
        tipo_forzado=PROYECTO,
        nota="piso a ~1/100 de lo medido",
    ),
    Clausula(
        clave="span_construction",
        resumen="construir un Span del pipeline no colapsó.",
        anclas=(Ancla("docs/verification/METODOLOGIA.md", 106, "Pisos de guardarrail"),),
        tipo_forzado=PROYECTO,
        nota="piso a ~1/100 de lo medido",
    ),
    Clausula(
        clave="price_key",
        resumen="resolver la clave de precio de un modelo no colapsó.",
        anclas=(Ancla("docs/verification/METODOLOGIA.md", 106, "Pisos de guardarrail"),),
        tipo_forzado=PROYECTO,
        nota="piso a ~1/100 de lo medido",
    ),
    Clausula(
        clave="ratelimiter",
        resumen="adquirir un token del bucket no colapsó.",
        anclas=(Ancla("docs/verification/METODOLOGIA.md", 106, "Pisos de guardarrail"),),
        tipo_forzado=PROYECTO,
        nota="piso a ~1/100 de lo medido",
    ),
    Clausula(
        clave="cache_hit_scaling",
        resumen="El coste de un hit de cache no crece con el tamaño del store.",
        anclas=(
            Ancla("docs/verification/METODOLOGIA.md", 104, "no puede crecer con el tamaño del estado"),
            Ancla("docs/verification/METODOLOGIA.md", 110, "La deuda visible vale más que el verde fingido"),
        ),
        tipo_forzado=PROYECTO,
        nota=(
            "FALSE visible y crónico hasta que el prune O(n) por llamada se amortice: "
            "issue #1 (sem. 15). La regla 3 de §7 autoriza exactamente este estado"
        ),
    ),
)


@lru_cache(maxsize=None)
def _contenido_en_tag(archivo: str) -> str | None:
    """Contenido del archivo tal como estaba en el tag v1.0.0, o None si no existía."""
    try:
        salida = subprocess.run(
            ["git", "show", f"{TAG}:{archivo}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return salida.stdout if salida.returncode == 0 else None


def resolver(clausula: Clausula) -> dict:
    """Verifica el ancla contra el archivo actual y contra el tag v1.0.0."""
    problemas: list[str] = []
    en_tag: list[bool] = []
    citas: list[str] = []

    for ancla in clausula.anclas:
        ruta = ancla.ruta()
        if not ruta.is_file():
            problemas.append(f"el archivo de ancla no existe: {ancla.archivo}")
            continue
        lineas = ruta.read_text().splitlines()
        if ancla.linea > len(lineas):
            problemas.append(f"{ancla.archivo}:{ancla.linea} está más allá del archivo ({len(lineas)} líneas)")
            continue
        actual = lineas[ancla.linea - 1]
        if ancla.texto not in actual:
            problemas.append(f"{ancla.archivo}:{ancla.linea} no contiene {ancla.texto!r}: {actual.strip()!r}")
        citas.append(f"{ancla.archivo}:{ancla.linea}")

        previo = _contenido_en_tag(ancla.archivo)
        if previo is None:
            if not clausula.tipo_forzado:
                problemas.append(f"no se pudo leer {ancla.archivo} en {TAG}: no se puede probar que sea preexistente")
            en_tag.append(False)
        else:
            en_tag.append(any(ancla.texto in ln for ln in previo.splitlines()))

    if clausula.tipo_forzado:
        tipo = clausula.tipo_forzado
    elif en_tag and all(en_tag):
        tipo = PREEXISTENTE
    else:
        tipo = DECISION

    return {
        "clave": clausula.clave,
        "resumen": clausula.resumen,
        "tipo": tipo,
        "citas": citas,
        "anclada_en_v1_0_0": bool(en_tag) and all(en_tag),
        "seccion": clausula.anclas[0].seccion if clausula.anclas else "",
        "nota": clausula.nota,
        "problemas": problemas,
    }


def resolver_todas() -> list[dict]:
    return [resolver(c) for c in CLAUSULAS]


def por_clave() -> dict[str, dict]:
    return {r["clave"]: r for r in resolver_todas()}
