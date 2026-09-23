from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ci_pack import EvidenceReport, collect, render, render_eval_smoke_job, run_lints

CORE_REF = "v0.7.0"


def _prompt(path: Path, *, ident: str = "p1", eval_ref: str | None = "evals/p1.jsonl") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = {"id": ident, "version": "0.1.0", "schema": "noop-v1"}
    if eval_ref is not None:
        fm["eval"] = eval_ref
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nCuerpo del prompt.\n")
    return path


def _consumer(tmp_path: Path, name: str, week: int) -> Path:
    repo = tmp_path / name
    (repo / "prompts").mkdir(parents=True)
    (repo / "evals").mkdir()
    _prompt(repo / "prompts" / "main.md", ident="main", eval_ref="evals/main.jsonl")
    (repo / "evals" / "main.jsonl").write_text(
        json.dumps({"prompt_id": "main", "prompt_version": "0.1.0", "input": {}, "expected": None, "criteria": {"type": "schema_match", "schema": "noop-v1"}}) + "\n"
    )
    _prompt(repo / "prompts" / "helper.txt", ident="helper", eval_ref=None)
    manifest = {
        "week": week,
        "name": name,
        "core_version": "0.7.0",
        "reused_modules": ["llm-client", "schema-validate", "test-kit", "ci-pack"],
        "new_surface": ["una cosita nueva"],
        "estimated_new_surface": 25,
    }
    (repo / "core-consumer.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return repo


class TestLints:
    def test_import_directo_de_proveedor(self, tmp_path: Path) -> None:
        f = tmp_path / "src" / "app.py"
        f.parent.mkdir(parents=True)
        f.write_text("import openai\nresp = openai.chat.completions.create(...)\n")
        report = run_lints([tmp_path])
        assert any("openai" in v and "llm_client" in v for v in report.violations)

    def test_prompt_inline(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text('PROMPT = """Eres un traductor experto. Traduce del español al inglés."""\n')
        report = run_lints([tmp_path])
        assert any("prompts con frontmatter" in v for v in report.violations)

    def test_secreto_en_claro(self, tmp_path: Path) -> None:
        f = tmp_path / "config.py"
        f.write_text("token = 'ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456'\n")
        report = run_lints([tmp_path])
        assert any("github_token" in v for v in report.violations)

    def test_repo_limpio(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("from llm_client import LlmClient\nprint('hola')\n")
        assert run_lints([tmp_path]).ok


class TestMetrics:
    def test_collect_y_render(self, tmp_path: Path) -> None:
        c1 = _consumer(tmp_path, "alpha", 7)
        c2 = _consumer(tmp_path, "beta", 2)
        spans = tmp_path / "spans"
        spans.mkdir()
        span = json.dumps({"consumer_repo": "alpha", "prompt_id": "main", "prompt_version": "0.1.0", "model_alias": "fast", "model": "m", "provider": "p", "cost_usd": "0.5", "status": "ok"})
        (spans / "alpha.jsonl").write_text(span + "\n" + span + "\n")
        (spans / "beta.jsonl").write_text(
            json.dumps({"consumer_repo": "beta", "prompt_id": "main", "prompt_version": "0.1.0", "model_alias": "fast", "model": "m", "provider": "p", "cost_usd": "0.25", "status": "ok"}) + "\n"
        )

        report = collect([c1, c2], spans_dir=spans)
        assert isinstance(report, EvidenceReport)
        assert report.repo_count == 2
        assert report.total_calls == 3
        assert report.total_cost_usd == 1.25
        assert report.prompts_with_eval == 2
        assert report.prompt_count == 4
        assert all(r.reuse_pct == 75 for r in report.weeks)

        html = render(report)
        assert "Página de evidencia" in html
        assert "alpha" in html and "beta" in html


class TestJobs:
    def test_workflow_yaml_parsea_y_clona_el_core(self) -> None:
        text = render_eval_smoke_job(core_ref=CORE_REF)
        data = yaml.safe_load(text)
        assert data["name"] == "eval-smoke"
        steps = data["jobs"]["eval-smoke"]["steps"]
        assert any(s.get("uses") == "actions/checkout@v4" for s in steps)
        clone = next(s for s in steps if "git clone" in s.get("run", ""))
        assert CORE_REF in clone["run"]
        assert "llm-dev-core.git" in clone["run"]

    def test_mismo_layout_que_el_workflow_real(self, tmp_path: Path) -> None:
        generated = render_eval_smoke_job()
        target = tmp_path / "eval-smoke.yml"
        target.write_text(generated)
        parsed = yaml.safe_load(target.read_text())
        assert parsed["jobs"]["eval-smoke"]["runs-on"] == "ubuntu-latest"

    def test_el_clone_no_se_envuelve_en_varias_lineas(self) -> None:
        generated = render_eval_smoke_job(core_ref=CORE_REF)
        clone = next(
            l.strip() for l in generated.splitlines() if "git clone" in l and"--branch" in l
        )
        assert "llm-dev-core.git ../llm-dev-core" in clone