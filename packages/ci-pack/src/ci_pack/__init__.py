"""ci_pack — lints, jobs CI y página de evidencia para la flota de consumidores.

`llm-dev-core` 0.7 (semana 7): los invariantes de §3 y las promesas de §2.1 que
`check_consumers.py` no cubre por coste bajo quedan aquí:
  - lint anti-imports (toda llamada a un LLM pasa por `llm-client`),
  - lint anti-secretos (nada en claro en código/prompts — motor `secure-base`),
  - lint anti-prompts-inline (los prompts viven en `/prompts` con frontmatter),
  - generador de jobs `eval-smoke` (conecta `test-kit.run` a un workflow),
  - `collect`/`render` de la página de evidencia (§10.1): reutilización, cobertura
    de evals, matriz repo × core y costo desde los spans de `llm-client`.
"""

from .job import DEFAULT_CORE_REF, render_eval_smoke_job
from .lints import LintReport, lint_imports, lint_inline_prompts, lint_secrets, run_lints
from .metrics import EvidenceReport, collect, render

__all__ = [
    "DEFAULT_CORE_REF",
    "EvidenceReport",
    "LintReport",
    "collect",
    "lint_imports",
    "lint_inline_prompts",
    "lint_secrets",
    "render",
    "render_eval_smoke_job",
    "run_lints",
]