# Metodología de verificación (v1.1)

Este archivo existe para que las mediciones tengan dónde citar el criterio cuando el
criterio **no** viene de un ADR. Sin él, el umbral vivía dentro del script de
medición y por lo tanto podía moverse con quien lo escribió.

## 1. Los tres estados de un claim

| estado | significa | cómo se gana |
| --- | --- | --- |
| `MEDIDO` | hay un artefacto, un comando y el número sale de ejecutarlo | `scripts/verification_baseline.py` |
| `DOCUMENTADO, NO VERIFICADO` | el repo lo afirma pero no existe artefacto que lo respalde | se escribe así en el README, sin `[x]` |
| `FALSO / ELIMINADO` | se midió y no se sostiene | se elimina la afirmación |

## 2. Regla del oráculo externo

Una afirmación sobre el estado del proyecto solo pasa a `MEDIDO` cuando su número
sale de un **oráculo externo**: un comando ejecutado, un archivo de la release, una
API de GitHub o PyPI, o el sistema de archivos. Quedan excluidos, siempre:

- el número que escribe el propio código que hace la medición;
- un manifiesto que el repo genera y después se cita a sí mismo;
- una estimación presentada como métrica;
- cualquier juicio sobre calidad, utilidad o estilo de una salida LLM.

Cuando no hay oráculo externo disponible, la afirmación se degrada a
`DOCUMENTADO, NO VERIFICADO`. No se estima y no se redondea a "parecido".

## 3. Cifra verificable

Una cifra escrita en un README es `MEDIDO` solo si está enlazada a una ejecución
guardada: un comando reproducible más un artefacto con el resultado. Un número
pegado a mano, por pequeño que sea, cuenta como `DOCUMENTADO, NO VERIFICADO`.

**Antes de exigir una ejecución, hay que clasificar la cifra.** No toda cifra es un
claim: un puerto, un código HTTP, una fecha o un número de semana no afirman nada
sobre el comportamiento del sistema, y exigirles una ejecución guardada infla el
recuento con afirmaciones que nadie hizo. `scripts/verification_baseline.py` separa
las categorías y solo verifica las de contrato —"N campos", "N ADRs", "N archivos"—,
que sí son afirmaciones sobre lo que el repo contiene. Las demás se declaran fuera
del criterio, con su categoría a la vista.

**El criterio de F3 tiene dos partes y las dos se ejecutan:**

1. Una cifra de contrato debe coincidir con su oráculo (`len(Span.model_fields)`,
   `docs/decisions/*.md`). Una discrepancia es un `FALSE`, y la fila dice cuál.
2. Una cifra de contrato que dependa de un número que cambia con el trabajo en curso
   no se escribe. Se escribe el comando que la produce. "107 tests" era cierto el día
   que se escribió y falso después; "el número exacto cambia, el comando es
   `make validate`" sigue siendo cierto.

## 3.1 Un cero que no dice de dónde viene no es un dato

La versión anterior de la página de evidencia imprimía `$0.0000` en las doce filas.
Eso mezclaba tres cosas que el lector no puede separar: una llamada que costó cero,
un repo del que no se tiene ninguna llamada, y un modelo cuyo precio nadie conoce.
`llm_client.pricing.cost_usd` devuelve `0` en los tres casos, porque así funcionaba
una tabla de precios con un único modelo gratis.

La regla que sale de ahí: **todo cero se rotula con su procedencia** —
`(spans)`, `(cassette · modelo en tabla de precios)`, `costo desconocido` o
`sin datos de llamada`. Un costo que no se sabe no se escribe como cero; se escribe
como `costo desconocido`. `model_price_known()` existe para que esa distinción sea
consultable desde código y no dependa de que alguien lea la página con cuidado.

## 4. Qué se mide y qué no

Se mide lo falsable por código: invariantes de datos, fidelidad de reconstrucción,
exhaustividad, clasificación de entradas, álgebra con reloj y presupuesto inyectados,
y la forma de las afirmaciones del propio repositorio.

**No** se mide calidad de salida de un modelo. No hay juez LLM, ni conjunto dorado,
ni N grande de ejemplos. Afirmar que un prompt "produce un buen informe" exige datos
de ejecución guardados; mientras no existan, esa afirmación no se escribe.

## 5. Tipo de cláusula

Cada medición del baseline cita su cláusula y el harness decide su tipo contra el
tag `v1.0.0`:

- `PREEXISTENTE`: el texto citado ya estaba en el tag. El contrato es de antes de
  este trabajo y su verificación significa algo sobre el historial.
- `DECISION v1.1`: el texto lo escribió este trabajo. Verificar que el código la
  cumple no dice nada sobre el pasado; dice que la decisión está implementada.
- `CRITERIO DE PROYECTO`: el umbral no viene de un ADR, sino de este documento.

Un instrumento no puede declararse `PREEXISTENTE` a sí mismo: lo decide `git show`.

## 6. Reproducibilidad

`make verify-baseline` escribe el JSON y el informe. El corpus excluye su propia
salida, así que dos corridas seguidas coinciden salvo la marca de tiempo; como el
corpus **sí** incluye el código del repositorio, el baseline es una foto del árbol y
`tests/test_verification_baseline.py` falla si el JSON commiteado no coincide con
una medición fresca.

## 7. Rendimiento: la forma es contrato, el número no

Hasta v1.1 "optimizado" no tenía oráculo: §4 excluye la calidad y ninguna cifra del
baseline medía velocidad. Esta sección abre ese hueco con tres reglas:

1. **Un tiempo absoluto no es contrato.** Depende del hardware de quien ejecute, así
   que ningún umbral se escribe en ops/s. Lo verificable es la **forma**: el coste por
   operación no puede crecer con el tamaño del estado cuando la operación promete ser
   O(1) — un hit de cache, un lookup de precio.
2. **Pisos de guardarrail, ~100× por debajo de lo medido.** Un piso no dice "es
   rápido"; dice "no se volvió grotescamente lento". Solo se rompe ante una regresión
   estructural (un O(n) que era O(1), un re-compile por línea), no ante un laptop
   lento o un runner saturado de CI.
3. **La deuda visible vale más que el verde fingido.** Una cláusula de rendimiento
   puede quedar `FALSE` de forma crónica hasta que el fix llegue: el informe la
   publica con su acción abierta, igual que F0 publicó sus defectos de código.

`scripts/verification_perf.py` (`make verify-perf`) mide y escribe
`docs/verification/{perf.json,PERF.md}`. Ninguna cifra del informe está escrita a
mano y las cláusulas de esta sección son `CRITERIO DE PROYECTO` por definición: el
tag `v1.0.0` no contiene ninguna de estas líneas.
