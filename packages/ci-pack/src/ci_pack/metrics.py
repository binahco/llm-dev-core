"""Página de evidencia (§10.1): reutilización, cobertura de evals, matriz y costo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

import yaml
from llm_client import Span

# Claves del frontmatter de un prompt (mismo contrato que check_consumers.py).
FM_KEYS = ("id", "version", "schema", "eval")
PROMPT_EXTS = (".md", ".txt", ".jinja", ".j2")

REUSE_TARGET_ABOVE = 70  # §2.1: superficie nueva ≤ 30% implica reutilización ≥ 70%.


@dataclass(frozen=True)
class WeekRow:
    repo: str
    week: int
    core_version: str
    reuse_pct: int
    reused_modules: list[str]
    prompts: int
    prompts_with_eval: int
    calls: int
    cost_usd: float


@dataclass(frozen=True)
class EvidenceReport:
    weeks: list[WeekRow]

    @property
    def repo_count(self) -> int:
        return len(self.weeks)

    @property
    def prompt_count(self) -> int:
        return sum(r.prompts for r in self.weeks)

    @property
    def prompts_with_eval(self) -> int:
        return sum(r.prompts_with_eval for r in self.weeks)

    @property
    def total_calls(self) -> int:
        return sum(r.calls for r in self.weeks)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.weeks), 6)

    @property
    def reuse_ok_repos(self) -> int:
        return sum(1 for r in self.weeks if r.reuse_pct >= REUSE_TARGET_ABOVE)

    def to_plain(self) -> dict:
        """Dict serializable (fields + derivadas) para respuestas JSON y HTML."""
        return {
            "repo_count": self.repo_count,
            "prompt_count": self.prompt_count,
            "prompts_with_eval": self.prompts_with_eval,
            "total_calls": self.total_calls,
            "total_cost_usd": self.total_cost_usd,
            "reuse_ok_repos": self.reuse_ok_repos,
            "threshold_reuse_pct": REUSE_TARGET_ABOVE,
            "weeks": [asdict(row) for row in self.weeks],
        }


def _load_yaml(path: Path) -> dict | None:
    try:
        data = yaml.safe_load(path.read_text())
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _frontmatter(path: Path) -> dict | None:
    lines = path.read_text(errors="ignore").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i, ln in enumerate(lines[1:], start=1) if ln.strip() == "---"), None)
    if end is None:
        return None
    data = yaml.safe_load("\n".join(lines[1:end]))
    return data if isinstance(data, dict) else None


def _coverage(repo: Path) -> tuple[int, int]:
    prompts_dir = repo / "prompts"
    if not prompts_dir.is_dir():
        return 0, 0
    files = [p for p in prompts_dir.rglob("*") if p.is_file() and p.suffix in PROMPT_EXTS]
    with_eval = 0
    for p in files:
        fm = _frontmatter(p)
        if fm is None or "eval" not in fm:
            continue
        ref = fm.get("eval")
        if isinstance(ref, str) and "{" not in ref and (repo / ref).is_file():
            with_eval += 1
    return with_eval, len(files)


def _spans(spans_dir: Path | None) -> list[Span]:
    if spans_dir is None or not spans_dir.exists():
        return []
    out: list[Span] = []
    for f in spans_dir.rglob("*.jsonl"):
        for line in f.read_text(errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                out.append(Span.model_validate_json(line))
            except Exception:  # noqa: BLE001
                continue
    return out


def collect(consumer_repos: list[Path], spans_dir: Path | None = None) -> EvidenceReport:
    rows: list[WeekRow] = []
    spans = _spans(spans_dir)

    for repo in consumer_repos:
        manifest = repo / "core-consumer.yml"
        if not manifest.is_file():
            continue
        data = _load_yaml(manifest)
        if data is None:
            continue
        name = str(data.get("name", repo.name))
        week = int(data.get("week", 0))
        core_version = str(data.get("core_version", "?"))
        reuse = max(0, 100 - int(data.get("estimated_new_surface", 100)))
        modules = list(data.get("reused_modules", ()))
        with_eval, total = _coverage(repo)
        repo_spans = [s for s in spans if s.consumer_repo == name or s.consumer_repo == repo.name]
        cost = float(sum(Decimal(s.cost_usd or 0) for s in repo_spans))
        rows.append(
            WeekRow(
                repo=repo.name,
                week=week,
                core_version=core_version,
                reuse_pct=reuse,
                reused_modules=modules,
                prompts=total,
                prompts_with_eval=with_eval,
                calls=len(repo_spans),
                cost_usd=round(cost, 6),
            )
        )

    rows.sort(key=lambda r: (r.week, r.repo))
    return EvidenceReport(weeks=rows)


def render(report: EvidenceReport) -> str:
    """Devuelve el HTML de la página de evidencia (§10.1)."""
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    rows = "".join(
        "<tr>"
        f"<td>{esc(r.repo)}</td><td>{r.week}</td><td>{esc(r.core_version)}</td>"
        f"<td>{r.reuse_pct}%</td><td>{esc(', '.join(r.reused_modules))}</td>"
        f"<td>{r.prompts_with_eval}/{r.prompts}</td><td>{r.calls}</td><td>${r.cost_usd:.4f}</td>"
        "</tr>"
        for r in report.weeks
    )
    return (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<title>llm-dev-core · página de evidencia</title>"
        "<style>body{font:14px/1.5 -apple-system,sans-serif;margin:2rem}table{border-collapse:collapse;"
        "width:100%}th,td{border:1px solid #ddd;padding:6px 10px;text-align:left}th{background:#f4f4f4}"
        ".ok{color:#0a7b0a;font-weight:700}</style></head><body>"
        "<h1>Página de evidencia — llm-dev-core</h1>"
        f"<p>{report.repo_count} consumidores · {report.prompt_count} prompts "
        f"(<span class=\"ok\">{report.prompts_with_eval} con dataset</span>) · "
        f"{report.total_calls} llamadas · acumulado <span class=\"ok\">${report.total_cost_usd:.4f}</span> · "
        f"{report.reuse_ok_repos}/{report.repo_count} en reutilización ≥ {REUSE_TARGET_ABOVE}%.</p>"
        "<table><thead><tr><th>repo</th><th>sem</th><th>core</th><th>reutilización</th>"
        "<th>módulos reutilizados</th><th>evals</th><th>llamadas</th><th>costo</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    )