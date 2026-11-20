"""Página de evidencia (§10.1): reutilización, cobertura de evals, matriz y costo."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

import yaml
from llm_client import Span
from llm_client.pricing import model_price_known

# Claves del frontmatter de un prompt (mismo contrato que check_consumers.py).
FM_KEYS = ("id", "version", "schema", "eval")
PROMPT_EXTS = (".md", ".txt", ".jinja", ".j2")

REUSE_TARGET_ABOVE = 70  # §2.1: superficie nueva ≤ 30% implica reutilización ≥ 70%.


@dataclass(frozen=True)
class CassetteUsage:
    """Calls and tokens read from a repo's cassettes, plus unknown-model control."""

    calls: int
    tokens_in: int
    tokens_out: int
    models_unknown: list[str]
    cost_explained: bool


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
    cassette_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_explained: bool = False


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
    def total_cassette_calls(self) -> int:
        return sum(r.cassette_calls for r in self.weeks)

    @property
    def total_tokens_in(self) -> int:
        return sum(r.tokens_in for r in self.weeks)

    @property
    def total_tokens_out(self) -> int:
        return sum(r.tokens_out for r in self.weeks)

    @property
    def rows_with_unknown_model(self) -> list[str]:
        return [r.repo for r in self.weeks if not r.cost_explained]

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


def _cassette_usage(repo: Path) -> CassetteUsage:
    """Lee el uso de tokens de las grabaciones (`cassettes/*.jsonl`) del repo.

    Los cassettes son respuestas reales del proveedor con su `usage`; son la única
    fuente de llamadas que existe hoy en la flota (ver ADR-6 §2). Se leen aparte de
    los spans porque su forma es `{model, request, response}` y no un `Span`.

    `models_unknown` lista los modelos cuyo precio no está en la tabla de precios. Es
    la diferencia entre "esta llamada costó $0" y "no sabemos cuánto costó y por eso
    sale 0": `cost_usd` devuelve 0 para cualquier modelo no listado, así que un
    modelo desconocido se camufla de modelo gratis.
    """
    calls = tokens_in = tokens_out = 0
    models: set[str] = set()
    cdir = repo / "cassettes"
    if not cdir.is_dir():
        return CassetteUsage(0, 0, 0, [], True)
    for f in sorted(cdir.glob("*.jsonl")):
        for line in f.read_text(errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            response = entry.get("response") or {}
            models.add(str(response.get("model") or entry.get("model") or ""))
            usage = response.get("usage") or {}
            calls += 1
            tokens_in += int(usage.get("input_tokens") or 0)
            tokens_out += int(usage.get("output_tokens") or 0)
    unknown = sorted(m for m in models if not model_price_known(m))
    return CassetteUsage(calls, tokens_in, tokens_out, unknown, not unknown)


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
        usage = _cassette_usage(repo)
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
                cassette_calls=usage.calls,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                cost_explained=usage.cost_explained,
            )
        )

    rows.sort(key=lambda r: (r.week, r.repo))
    return EvidenceReport(weeks=rows)


def _cost_cell(row: WeekRow) -> str:
    """Celdas de costo con procedencia explícita, para que un 0 no se lea como un hueco.

    Tres estados que la versión anterior confundía en un solo `$0.0000`:

    - `spans guardados`: el costo viene de spans con `cost_usd` real.
    - `cassette · modelo conocido`: no hay spans, pero las grabaciones sí traen `usage`
      y el modelo **está** en la tabla de precios, así que el 0 es un precio medido.
    - `costo desconocido`: el modelo de las grabaciones no está en la tabla de
      precios. `cost_usd` devuelve 0 para lo desconocido, así que este 0 no significa
      nada y se escribe como tal en vez de disfrazarse de dato.
    """
    if row.calls:
        return f"${row.cost_usd:.4f} <small>(spans)</small>"
    if row.cassette_calls and row.cost_explained:
        return f"${row.cost_usd:.4f} <small>(cassette · modelo en tabla de precios)</small>"
    if row.cassette_calls:
        return "<span class=\"warn\">$? — modelo fuera de la tabla de precios</span>"
    return "<span class=\"warn\">sin datos de llamada</span>"


def render(report: EvidenceReport) -> str:
    """Devuelve el HTML de la página de evidencia (§10.1)."""
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    rows = "".join(
        "<tr>"
        f"<td>{esc(r.repo)}</td><td>{r.week}</td><td>{esc(r.core_version)}</td>"
        f"<td>{r.reuse_pct}%</td><td>{esc(', '.join(r.reused_modules))}</td>"
        f"<td>{r.prompts_with_eval}/{r.prompts}</td><td>{r.calls}</td>"
        f"<td>{r.cassette_calls}</td><td>{r.tokens_in}/{r.tokens_out}</td>"
        f"<td>{_cost_cell(r)}</td>"
        "</tr>"
        for r in report.weeks
    )
    return (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<title>llm-dev-core · página de evidencia</title>"
        "<style>body{font:14px/1.5 -apple-system,sans-serif;margin:2rem}table{border-collapse:collapse;"
        "width:100%}th,td{border:1px solid #ddd;padding:6px 10px;text-align:left}th{background:#f4f4f4}"
        ".ok{color:#0a7b0a;font-weight:700}.warn{color:#a15c00;font-weight:700}"
        "small{color:#666}</style></head><body>"
        "<h1>Página de evidencia — llm-dev-core</h1>"
        f"<p>{report.repo_count} consumidores · {report.prompt_count} prompts "
        f"(<span class=\"ok\">{report.prompts_with_eval} con dataset</span>) · "
        f"{report.total_calls} llamadas con span guardado · "
        f"{report.total_cassette_calls} llamadas grabadas en cassettes · "
        f"{report.total_tokens_in} tokens in / {report.total_tokens_out} tokens out · "
        f"{report.reuse_ok_repos}/{report.repo_count} en reutilización ≥ {REUSE_TARGET_ABOVE}%.</p>"
        "<table><thead><tr><th>repo</th><th>sem</th><th>core</th><th>reutilización</th>"
        "<th>módulos reutilizados</th><th>evals</th><th>llamadas (span)</th>"
        "<th>llamadas (cassette)</th><th>tokens in/out</th><th>costo</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "<p><small>Una llamada con span es una ejecución instrumentada por "
        "`llm-client`. Una llamada en cassette es una grabación de proveedor: trae "
        "<code>usage</code> real, pero no pasó por el pipeline del core, así que no "
        "tiene <code>latency_ms</code> ni <code>retry_count</code>. El costo solo se "
        "declara cuando el modelo está en la tabla de precios; si no, se escribe "
        "&quot;costo desconocido&quot; en vez de 0.</small></p>"
        "</body></html>"
    )