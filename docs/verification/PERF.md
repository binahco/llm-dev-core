# Baseline de rendimiento (METODOLOGIA §7)

Generado por `scripts/verification_perf.py` el 2026-11-20.
Artefacto de datos: `docs/verification/perf.json` (se escribe en cada ejecución).

La forma es contrato y el número no (§7.1): seis pisos de guardarrail (§7.2) y una
cláusula de forma sobre el hit del cache. Ninguna cifra de este documento está
escrita a mano: todas salen de la ejecución anterior. Un `FALSE` aquí es deuda
publicada (§7.3), no un fallo de la suite.

| medición | tipo de cláusula | ancla | veredicto | evidencia medida | acción |
| --- | --- | --- | --- | --- | --- |
| parser_corpus | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:106` | TRUE | 5821.1 docs/s (piso 40); 0.0076 s de mejor de 3 | — |
| detect_lines | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:106` | TRUE | 156112.0 líneas/s (piso 3500); 0.0468 s de mejor de 3 | — |
| validate_text | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:106` | TRUE | 558821.7 validaciones/s (piso 5000); 0.0036 s de mejor de 3 | — |
| span_construction | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:106` | TRUE | 352960.9 spans/s (piso 3000); 0.0142 s de mejor de 3 | — |
| price_key | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:106` | TRUE | 13183914.4 lookups/s (piso 75000); 0.0004 s de mejor de 3 | — |
| ratelimiter | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:106` | TRUE | 6941836.4 acquires/s (piso 60000); 0.0014 s de mejor de 3 | — |
| cache_hit_scaling | CRITERIO DE PROYECTO | `docs/verification/METODOLOGIA.md:104`, `docs/verification/METODOLOGIA.md:110` | TRUE | 1.88 µs/hit con store=1 vs 1.84 µs/hit con store=2500 (ratio 1.0×, umbral 10×) sobre 2000 hits | — |

Totales: 7 `TRUE`, 0 `FALSE`.

## Qué NO prueba este baseline

- Corre en una máquina, mejor de 3: es una foto de forma y de órdenes de magnitud,
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
