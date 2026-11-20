# Baseline de verificación (F0-F2.1)

Generado por `scripts/verification_baseline.py` el 2026-11-20.
Artefacto de datos: `docs/verification/baseline.json` (se escribe en cada ejecución).

Cada fila cita el archivo y la línea del contrato que mide, el tipo de esa cláusula, el
oráculo que produce el número y la acción que se abre si el veredicto no es `TRUE`.
Ninguna cifra de este documento está escrita a mano: todas salen de la ejecución anterior.

El tipo lo decide `git show v1.0.0:<archivo>`, no el autor: `PREEXISTENTE` significa que
el texto ya estaba en el tag, `DECISION v1.1` que lo escribió este trabajo, y
`CRITERIO DE PROYECTO` que el umbral viene de `docs/verification/METODOLOGIA.md`.

| medición | tipo de cláusula | ancla | veredicto | evidencia medida | acción |
| --- | --- | --- | --- | --- | --- |
| slice_fidelity | DECISION v1.1 | `docs/decisions/0009-parser-io-contract.md:58` | TRUE | 212/212 secciones (100.0%) cumplen body == lines[line_start:line_end]; 492 líneas con contexto fuera de toda sección; 35 H1 y 0 H2+ ausentes del resultado | — |
| idempotence | PREEXISTENTE | `docs/decisions/0009-parser-io-contract.md:50` | TRUE | 48/48 documentos idénticos en dos parses del mismo archivo | — |
| empty_heading | DECISION v1.1 | `docs/decisions/0009-parser-io-contract.md:67` | TRUE | excepción=None; secciones devueltas=['Sección vacía', 'Con contenido']; sección vacía conservada=True, rango coherente=True | — |
| schema_enumeration | PREEXISTENTE | `docs/decisions/0002-schema-validate-contract.md:37` | TRUE | 14/14 entradas clasificadas como espera ADR-2 §2 | — |
| detectors | DECISION v1.1 | `docs/decisions/0003-secure-base-contract.md:22`, `docs/decisions/0003-secure-base-contract.md:37` | TRUE | 9/9 positivos; 0 hallazgos en 7398 líneas de producción; 0/10 negativos duros marcados | — |
| time_invariants | PREEXISTENTE | `docs/decisions/0007-cache-ratelimit-contract.md:21`, `docs/decisions/0007-cache-ratelimit-contract.md:50`, `docs/decisions/0008-bot-base-contract.md:72` | TRUE | TTL respetado=True; bucket 2.0→2.0; run_tasks 1ª=ok, 2ª=skipped, tras 90.000 s=ok | — |
| span_contract | PREEXISTENTE | `docs/decisions/0001-llm-client-contract.md:58` | TRUE | 20 campos en código contra 20 enumerados en ADR-1 §2 (línea 58); faltan=[], sobran=[] | — |
| evidence_self_audit | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:52`, `docs/decisions/0006-ci-pack-contract.md:47` | TRUE | 15 filas, 15 con datos de llamada: 49 en cassettes + 0 con span; 332170 tokens in / 13474 out; filas con costo desconocido=0 | — |
| docs_claims | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:29`, `docs/verification/METODOLOGIA.md:35` | TRUE | 17 cifras de contrato en 15 READMEs, 17 coinciden con su oráculo y 0 son falsas; el resto de cifras son {'identificador': 34, 'cronologia': 33, 'contrato': 17, 'http': 15, 'puerto': 14, 'referencia': 6, 'fecha': 6} y no son claims | — |

Totales: 9 `TRUE`, 0 `PARCIAL`, 0 `FALSE`.

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
