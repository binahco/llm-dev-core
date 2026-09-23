"""Generador de jobs `eval-smoke` (conecta `test-kit.run` a un workflow de CI).

Prerrequisito de CI: los consumidores dependen del core por path editable
(`../llm-dev-core`), así que el job clona la versión exacta del core al lado
antes de `uv sync --frozen`. Esto hace reproducible el patrón que hasta la
semana 6 se copiaba a mano (retrofit #0).
"""

from __future__ import annotations

import yaml

DEFAULT_CORE_REF = "v0.7.0"
DEFAULT_TEST_CMD = "uv run pytest tests/test_replay.py -q"


def render_eval_smoke_job(
    *,
    test_command: str = DEFAULT_TEST_CMD,
    core_ref: str = DEFAULT_CORE_REF,
    name: str = "eval-smoke",
) -> str:
    """Devuelve el YAML del workflow `eval-smoke` para un consumidor."""
    workflow = {
        "name": name,
        "on": {"pull_request": None, "push": {"branches": ["main"]}},
        "jobs": {
            name: {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "core en path editable (mismo layout local)",
                        "run": f"git clone --quiet --depth 1 --branch {core_ref} https://github.com/binahco/llm-dev-core.git ../llm-dev-core",
                    },
                    {"uses": "astral-sh/setup-uv@v6"},
                    {"run": "uv sync --frozen"},
                    {"name": "evals en verde (replay determinista, sin LLM — D4)", "run": test_command},
                ],
            }
        },
    }
    return yaml.safe_dump(workflow, sort_keys=False, allow_unicode=True, default_flow_style=False)