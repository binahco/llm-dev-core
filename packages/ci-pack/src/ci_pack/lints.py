"""Lints de invariantes de §3 que no cubre `check_consumers.py` (coste bajo día 1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from secure_base import assert_redacted

# SDKs de proveedores LLM externos: si un repo los importa fuera de `llm_client`,
# está violando la regla 1 de §3 (toda llamada a un LLM pasa por el cliente del core).
PRODUCER_SDKS = (
    "openai",
    "anthropic",
    "google.generativeai",
    "google_genai",
    "cohere",
    "mistralai",
    "groq",
    "replicate",
    "together",
    "ai21",
)

IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(" + "|".join(re.escape(s) for s in PRODUCER_SDKS) + r")(?:\.|$)",
    re.MULTILINE,
)

# Heurística de prompt-inline: literales largos con marcas de instrucción LLM.
PROMPT_HINTS = (
    "actúa como",
    "actua como",
    "eres ",
    "dado el siguiente",
    "you are ",
    "act as",
    "system prompt",
    "respond only",
)
INLINE_RE = re.compile(
    r"""(?:\"\"\"|''')([\s\S]{0,4000}?)(?:\"\"\"|''')""",
    re.MULTILINE,
)

# Directorios que nunca se auditan: tooling, cachés, dependencias y artefactos de
# desarrollo (tests/scripts con fixtures falsos). Cassettes/prompts/evals/src SÍ se
# auditan: simulan o contienen lo que realmente cruza al proveedor (§3.1).
SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "dist", "build", ".eggs", "tests", "scripts"}


@dataclass
class LintReport:
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def summary(self) -> str:
        if self.ok:
            return "ci-pack: lints OK"
        return f"ci-pack: {len(self.violations)} violacion(es)\n" + "\n".join(f"  - {v}" for v in self.violations)


def _iter_py(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            if p.suffix == ".py":
                files.append(p)
            continue
        for f in p.rglob("*.py"):
            if "llm_client" not in f.parts and f.parent.name not in SKIP_DIRS and not any(part in SKIP_DIRS for part in f.parts):
                files.append(f)
    return files


def lint_imports(paths: list[Path]) -> LintReport:
    """Regla 1 de §3: importar un SDK de proveedor fuera de `llm-client` es violación."""
    report = LintReport()
    for f in _iter_py(paths):
        for m in IMPORT_RE.finditer(f.read_text(errors="ignore")):
            report.violations.append(
                f"{f}: import directo del SDK '{m.group(1)}' — toda llamada pasa por llm_client"
            )
    return report


def lint_inline_prompts(paths: list[Path]) -> LintReport:
    """Regla 2 de §3: los prompts viven en `/prompts` (frontmatter), no en string literals."""
    report = LintReport()
    for f in _iter_py(paths):
        text = f.read_text(errors="ignore")
        for block in INLINE_RE.findall(text):
            lowered = block.lower()
            if any(hint in lowered for hint in PROMPT_HINTS):
                report.violations.append(
                    f"{f}: literal largo con marcas de prompt — muévelo a /prompts con frontmatter"
                )
                break
    return report


def lint_secrets(paths: list[Path]) -> LintReport:
    """Regla 1 de §3.1: secretos en claro en código o prompts son violación (motor secure-base)."""
    report = LintReport()
    for root in paths:
        if not root.exists():
            continue
        candidates: list[Path] = []
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for f in root.rglob("*"):
                if not f.is_file() or f.suffix not in (".py", ".md", ".yml", ".yaml", ".json", ".jsonl"):
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                candidates.append(f)
        for f in candidates:
            text = f.read_text(errors="ignore")
            for finding in assert_redacted(text):
                report.violations.append(
                    f"{f}:{finding.line}: {finding.type} en claro — redáctalos antes de commitear"
                )
    return report


def run_lints(paths: list[Path]) -> LintReport:
    report = LintReport()
    for lint in (lint_imports, lint_inline_prompts, lint_secrets):
        report.violations.extend(lint(paths).violations)
    return report