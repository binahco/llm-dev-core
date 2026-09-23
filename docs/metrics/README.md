# Métricas

Datos crudos y agregados de la página de evidencia (§10.1).

- `evidence.html` — el dashboard generado por `scripts/collect_metrics.py` (ci-pack,
  sem. 7): reutilización por semana, cobertura de evals, matriz repo × core, llamadas y
  costo acumulado desde los spans de `llm-client`. Se regenera en cada `make validate`.

Para regenerarlo a mano sobre consumidores concretos:

```bash
uv run python scripts/collect_metrics.py --self-auto   # detecta los repos en ../
uv run python scripts/collect_metrics.py ../commit-cli ../ci-scribe --spans ..
```