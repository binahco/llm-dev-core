#!/usr/bin/env python3
"""check_consumers.py — validación ejecutable de ARCHITECTURE.md §3/§2.1.

Modos:
  --self              valida este repo: estructura, plantillas, ADR-0.
  <ruta> ...          valida repos consumidores: core-consumer.yml,
                      prompts con frontmatter y evals referenciados.

Salida: 0 = ok · 1 = inválido · 2 = uso incorrecto.
Enforcement: `make validate` en local y workflow ci.yml.

Nota: el lint anti-imports y la agregación de métricas llegan con ci-pack
(sem. 6); aquí solo lo barato que §3 exige desde el día 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("error: falta PyYAML — ejecuta `uv sync`\n")
    raise SystemExit(1)


REQUIRED_DIRS = (
    "packages",
    "templates",
    "scripts",
    "docs/decisions",
    "docs/metrics",
    "docs/runbooks",
)

REQUIRED_TEMPLATES = (
    "consumer-readme.md",
    "core-consumer.yml",
    "prompt.md",
    "eval-dataset.jsonl",
    "retrofit-issue.md",
)

INT_KEYS = ("week", "estimated_new_surface")
STR_KEYS = ("name", "core_version")
LIST_KEYS = ("reused_modules", "new_surface")

FRONTMATTER_KEYS = ("id", "version", "schema", "eval")

PROMPT_EXTS = (".md", ".txt", ".jinja", ".j2")


def _parse_block(block: list[str], path: Path) -> tuple[dict | None, str | None]:
    try:
        data = yaml.safe_load("\n".join(block))
    except Exception as exc:  # noqa: BLE001
        return None, f"{path}: YAML inválido: {exc}"
    if not isinstance(data, dict):
        return None, f"{path}: se esperaba un mapa YAML"
    return data, None


def _load_yaml(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = yaml.safe_load(path.read_text())
    except Exception as exc:  # noqa: BLE001
        return None, f"{path}: YAML inválido: {exc}"
    if not isinstance(data, dict):
        return None, f"{path}: se esperaba un mapa YAML"
    return data, None


def _frontmatter(path: Path) -> tuple[dict | None, str | None]:
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return None, f"{path}: falta frontmatter (primera línea '---')"
    end = next((i for i, ln in enumerate(lines[1:], start=1) if ln.strip() == "---"), None)
    if end is None:
        return None, f"{path}: frontmatter sin cierre '---'"
    return _parse_block(lines[1:end], path)


def _manifest_errors(path: Path) -> list[str]:
    errors: list[str] = []
    data, err = _load_yaml(path)
    if err:
        return [err]
    assert data is not None

    for key in (*STR_KEYS, *INT_KEYS, *LIST_KEYS):
        if key not in data:
            errors.append(f"{path}: falta clave '{key}'")

    for key in INT_KEYS:
        if key in data and not isinstance(data[key], int):
            errors.append(f"{path}: '{key}' debe ser entero")
    if "week" in data and isinstance(data.get("week"), int) and data["week"] <= 0:
        errors.append(f"{path}: 'week' debe ser > 0")
    if "estimated_new_surface" in data and isinstance(data.get("estimated_new_surface"), int):
        if not 0 <= data["estimated_new_surface"] <= 100:
            errors.append(f"{path}: 'estimated_new_surface' debe estar entre 0 y 100")

    for key in LIST_KEYS:
        if key in data and not (
            isinstance(data[key], list) and all(isinstance(x, str) for x in data[key])
        ):
            errors.append(f"{path}: '{key}' debe ser una lista de strings")
    if "reused_modules" in data and not data["reused_modules"]:
        errors.append(f"{path}: 'reused_modules' no puede estar vacía")

    if "eval_budget_usd" in data and not isinstance(data["eval_budget_usd"], (int, float)):
        errors.append(f"{path}: 'eval_budget_usd' debe ser un número (clave opcional)")

    return errors


def _errors_self(repo: Path) -> list[str]:
    errors: list[str] = []

    for rel in REQUIRED_DIRS:
        if not (repo / rel).is_dir():
            errors.append(f"falta directorio requerido: {rel}/")

    for name in REQUIRED_TEMPLATES:
        if not (repo / "templates" / name).is_file():
            errors.append(f"falta plantilla: templates/{name}")

    manifest = repo / "templates" / "core-consumer.yml"
    if manifest.is_file():
        errors += _manifest_errors(manifest)

    prompt_template = repo / "templates" / "prompt.md"
    if prompt_template.is_file():
        data, err = _frontmatter(prompt_template)
        if err:
            errors.append(err)
        elif data is not None:
            for key in FRONTMATTER_KEYS:
                if key not in data:
                    errors.append(f"templates/prompt.md: frontmatter sin clave '{key}'")

    jsonl = repo / "templates" / "eval-dataset.jsonl"
    if jsonl.is_file():
        for lineno, line in enumerate(jsonl.read_text().splitlines(), start=1):
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"templates/eval-dataset.jsonl: línea {lineno} no es JSON: {exc}")

    adr = repo / "docs" / "decisions" / "0000-stack.md"
    if not adr.is_file():
        errors.append("falta ADR-0: docs/decisions/0000-stack.md")
    else:
        text = adr.read_text()
        if "Estado:" not in text or "aceptada" not in text:
            errors.append("ADR-0 debe declarar 'Estado: aceptada'")

    return errors


def _errors_consumer(repo: Path) -> list[str]:
    errors: list[str] = []

    manifest = repo / "core-consumer.yml"
    if not manifest.is_file():
        errors.append(f"{repo}: falta core-consumer.yml en la raíz")
        return errors
    errors += _manifest_errors(manifest)

    readme = repo / "README.md"
    if not readme.is_file():
        errors.append(f"{repo}: falta README.md")
    elif "Recicla de" not in readme.read_text():
        errors.append(f"{repo}: README.md sin sección 'Recicla de'")

    prompts = repo / "prompts"
    if not prompts.is_dir():
        errors.append(f"{repo}: falta directorio 'prompts/'")
        return errors

    prompt_files = [p for p in prompts.rglob("*") if p.is_file() and p.suffix in PROMPT_EXTS]
    if not prompt_files:
        errors.append(f"{repo}: prompts/ sin archivos con extensión {', '.join(PROMPT_EXTS)}")

    for prompt in prompt_files:
        data, err = _frontmatter(prompt)
        if err:
            errors.append(err)
            continue
        assert data is not None
        for key in FRONTMATTER_KEYS:
            if key not in data:
                errors.append(f"{prompt}: frontmatter sin clave '{key}'")
        eval_ref = data.get("eval")
        if isinstance(eval_ref, str) and "{" not in eval_ref and not (repo / eval_ref).is_file():
            errors.append(f"{prompt}: eval referenciado no existe: {eval_ref}")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("uso: check_consumers.py --self | <ruta_consumidor> ...", file=sys.stderr)
        return 2

    targets: list[tuple[str, Path | None]] = []
    if "--self" in args:
        targets.append(("self", None))
    for arg in args:
        if arg == "--self" or (arg == "." and "--self" in args):
            continue
        targets.append((arg, Path(arg)))

    failed: list[str] = []
    for label, path in targets:
        if path is None:
            errs = _errors_self(Path("."))
        elif path.is_dir():
            errs = _errors_consumer(path)
        else:
            errs = [f"{path}: no es un directorio"]
        for msg in errs:
            print(f"{label}: {msg}", file=sys.stderr)
        if errs:
            failed.append(label)

    if failed:
        print(f"check_consumers: {len(failed)} target(s) con errores", file=sys.stderr)
        return 1

    print(f"check_consumers: OK ({', '.join(label for label, _ in targets)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())