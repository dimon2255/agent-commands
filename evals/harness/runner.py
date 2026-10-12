"""Runs a skill's eval suite: subprocess per attempt, classification, grading, reporting."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .contract import validate_envelope
from .graders import Grade, GradeContext, load_custom_module, run_metric
from .pricing import add_usage, cost_usd, empty_usage
from .report import render_markdown, summarize

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
RESULTS_DIR = REPO_ROOT / "evals" / "results" / "api"


@dataclass
class SkillSuite:
    name: str
    root: Path
    config: dict
    cases: list[dict]
    entrypoint: Path
    custom_module: Any = None

    @property
    def metrics(self) -> list[dict]:
        return list(self.config.get("metrics", []))


@dataclass
class RunOptions:
    model: str = "claude-opus-5-5"
    effort: str | None = None
    judge_model: str = "claude-opus-5-5"
    reps: int = 1
    concurrency: int = 4
    limit: int | None = None
    case_filter: str | None = None
    tag_filter: str | None = None
    allow_model_mismatch: bool = False
    out_dir: Path | None = None
    resume: Path | None = None
    results_root: Path | None = None  # defaults to evals/results/api
    update_latest: bool = True  # False for comparison runs that must not replace latest/
    extra_env: dict[str, str] = field(default_factory=dict)


def validate_config(config: dict) -> list[str]:
    """Return config problems; a misspelt threshold must fail loudly, not silently disable a gate."""
    problems = [f"missing {key!r}" for key in ("skill", "entrypoint", "cases", "metrics") if key not in config]
    if problems:
        return problems
    names = [m.get("name") for m in config["metrics"]]
    if len(set(names)) != len(names):
        problems.append("duplicate metric names")
    for name in (config.get("thresholds") or {}):
        if name not in names:
            problems.append(f"threshold names unknown metric {name!r}")
    return problems


def load_suite(skill_dir: Path) -> SkillSuite:
    skill_dir = Path(skill_dir).resolve()
    cfg_path = skill_dir / "evals" / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"{skill_dir.name}: no evals/config.yaml")
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    for problem in validate_config(config):
        raise ValueError(f"{cfg_path}: {problem}")
    cases_path = skill_dir / config["cases"]
    cases: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(cases_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        for key in ("id", "input", "expected"):
            if key not in case:
                raise ValueError(f"{cases_path}:{i}: case missing {key!r}")
        if case["id"] in seen:
            raise ValueError(f"{cases_path}:{i}: duplicate case id {case['id']!r}")
        seen.add(case["id"])
        cases.append(case)
    custom = None
    if config.get("graders_module"):
        custom = load_custom_module(skill_dir / config["graders_module"])
    return SkillSuite(
        name=config["skill"],
        root=skill_dir,
        config=config,
        cases=cases,
        entrypoint=skill_dir / config["entrypoint"],
        custom_module=custom,
    )


def discover_suites(repo_root: Path = REPO_ROOT) -> list[SkillSuite]:
    suites = []
    for d in sorted((repo_root / "skills").iterdir()):
        if d.is_dir() and (d / "evals" / "config.yaml").exists():
            suites.append(load_suite(d))
    return suites


# --------------------------------------------------------------------------- grading


def grade_output(suite: SkillSuite, case: dict, output: Any, meta: dict, judge: Any) -> dict[str, Grade]:
    ctx = GradeContext(case=case, output=output, meta=meta, judge=judge, custom_module=suite.custom_module)
    return {m["name"]: run_metric(m, ctx) for m in suite.metrics}


def smoke(suite: SkillSuite) -> dict:
    """Oracle + null baseline through the graders, no API calls.

    Oracle: each case's expected.gold_output must pass every deterministic metric.
    Null: the configured null_output must fail at least one deterministic metric per case.
    llm_rubric metrics are skipped here because they need a judge.
    """
    det_metrics = [m for m in suite.metrics if m["grader"] != "llm_rubric"]
    oracle_fail: list[str] = []
    null_pass: list[str] = []
    null_unfalsifiable: list[str] = []
    meta = {"skill": suite.name, "status": "ok", "served_model": "oracle"}
    null_output = suite.config.get("null_output", None)
    for case in suite.cases:
        gold = case.get("expected", {}).get("gold_output")
        if gold is None:
            oracle_fail.append(f"{case['id']}: no expected.gold_output")
        else:
            ctx = GradeContext(case=case, output=gold, meta=meta, custom_module=suite.custom_module)
            for m in det_metrics:
                g = run_metric(m, ctx)
                if g.na:
                    continue  # metric does not apply to this case; nothing to verify
                if not g.passed:
                    oracle_fail.append(f"{case['id']}/{m['name']}: {g.evidence}")
        ctx = GradeContext(case=case, output=null_output, meta=meta, custom_module=suite.custom_module)
        applicable = [g for g in (run_metric(m, ctx) for m in det_metrics) if not g.na]
        if not applicable:
            null_unfalsifiable.append(case["id"])  # no deterministic metric can reject a null answer here
        elif all(g.passed for g in applicable):
            null_pass.append(case["id"])
    return {
        "skill": suite.name,
        "cases": len(suite.cases),
        "deterministic_metrics": [m["name"] for m in det_metrics],
        "oracle_failures": oracle_fail,
        "null_baseline_passes": null_pass,
        "null_unfalsifiable": null_unfalsifiable,
        "ok": not oracle_fail and not null_pass and not null_unfalsifiable,
    }


# --------------------------------------------------------------------------- running


def _run_script(suite: SkillSuite, case: dict, rep: int, opts: RunOptions, workdir: Path) -> tuple[str, dict]:
    """Run the entrypoint once. Returns ("row", row) or ("error", error_row)."""
    attempt_dir = workdir / f"{case['id']}-r{rep}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    input_path = attempt_dir / "input.json"
    input_path.write_text(json.dumps(case["input"], ensure_ascii=False, indent=2), encoding="utf-8")
    cmd = [sys.executable, str(suite.entrypoint), "--input", str(input_path), "--json", "--model", opts.model]
    if opts.effort:
        cmd += ["--effort", opts.effort]
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    env.update(opts.extra_env)
    timeout = int(suite.config.get("timeout_seconds", 300))
    base = {"case_id": case["id"], "rep": rep, "tags": case.get("tags", [])}
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
            timeout=timeout, cwd=str(suite.root),
        )
    except subprocess.TimeoutExpired:
        return "error", {**base, "failure_class": "timeout", "message": f"exceeded {timeout}s wall clock"}
    wall_ms = int((time.perf_counter() - t0) * 1000)
    (attempt_dir / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        return "error", {**base, "failure_class": "crash", "message": f"exit {proc.returncode}: {(proc.stderr or '')[-800:]}"}
    try:
        env_obj = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return "error", {**base, "failure_class": "unparseable_stdout", "message": f"{exc}: {proc.stdout[-400:]}"}
    problems = validate_envelope(env_obj)
    if problems:
        return "error", {**base, "failure_class": "contract_violation", "message": "; ".join(problems)}
    meta = env_obj["meta"]
    if meta["status"] == "error":
        return "error", {**base, "failure_class": "api_error", "message": json.dumps(env_obj.get("error"))[:800]}
    served = meta.get("served_model")
    if not served:
        return "error", {**base, "failure_class": "served_model_missing", "message": "envelope has no meta.served_model"}
    if served != opts.model and not opts.allow_model_mismatch:
        # Exact match: current model IDs carry no date suffix, and a prefix match would let
        # claude-opus-5 be served (and priced) as claude-opus-5-5.
        return "error", {**base, "failure_class": "served_model_mismatch", "message": f"asked {opts.model}, served {served}"}
    row = {
        **base,
        "status": meta["status"],
        "stop_reason": meta.get("stop_reason"),
        "served_model": served,
        "usage": meta.get("usage"),
        "cost_usd": cost_usd(served, meta.get("usage")),
        "latency_ms": meta.get("latency_ms"),
        "wall_ms": wall_ms,
        "calls": len(meta.get("calls") or []),
        "envelope": env_obj,
    }
    return "row", row


def _display_path(p: Path) -> str:
    """Repo-relative when inside the repo, absolute otherwise (fixtures, temp dirs)."""
    try:
        return str(p.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p.resolve())


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Runner:
    def __init__(self, suite: SkillSuite, opts: RunOptions, judge: Any = None):
        self.suite = suite
        self.opts = opts
        self.judge = judge

    def select_cases(self) -> list[dict]:
        cases = list(self.suite.cases)
        if self.opts.case_filter:
            import fnmatch

            cases = [c for c in cases if fnmatch.fnmatch(c["id"], self.opts.case_filter)]
        if self.opts.tag_filter:
            cases = [c for c in cases if self.opts.tag_filter in (c.get("tags") or [])]
        if self.opts.limit:
            cases = cases[: self.opts.limit]
        return cases

    def run(self) -> tuple[Path, dict]:
        suite, opts = self.suite, self.opts
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        results_root = opts.results_root or RESULTS_DIR
        out_dir = opts.resume or opts.out_dir or (results_root / suite.name / stamp)
        out_dir.mkdir(parents=True, exist_ok=True)
        traj_dir = out_dir / "trajectories"
        traj_dir.mkdir(exist_ok=True)
        workdir = results_root / suite.name / "work" / stamp
        cases = self.select_cases()

        rows = _read_jsonl(out_dir / "results.jsonl") if opts.resume else []
        errors = _read_jsonl(out_dir / "errors.jsonl") if opts.resume else []
        done = {(r["case_id"], r["rep"]) for r in rows}
        jobs = [(c, rep) for c in cases for rep in range(1, opts.reps + 1) if (c["id"], rep) not in done]
        # An attempt that errored last time is retried now, so its old error row must go;
        # error rows for attempts outside this run's selection are kept.
        retrying = {(c["id"], rep) for c, rep in jobs}
        errors = [e for e in errors if (e["case_id"], e["rep"]) not in retrying]
        run_meta = {
            "model": opts.model, "effort": opts.effort, "judge_model": opts.judge_model if self.judge else None,
            "cases": len(cases), "reps": opts.reps, "concurrency": opts.concurrency,
            "started_at": datetime.now(UTC).isoformat(timespec="seconds"), "entrypoint": _display_path(suite.entrypoint),
            "python": sys.version.split()[0],
        }
        print(f"[{suite.name}] {len(jobs)} attempt(s) ({len(cases)} cases x {opts.reps} reps) -> {out_dir}", file=sys.stderr)

        def work(job):
            case, rep = job
            kind, payload = _run_script(suite, case, rep, opts, workdir)
            if kind == "row":
                env_obj = payload.pop("envelope")
                meta = env_obj["meta"]
                grades: dict[str, Grade] = {}
                if payload["status"] == "ok":
                    grades = grade_output(suite, case, env_obj["output"], meta, self.judge)
                elif payload["status"] == "truncated" and env_obj.get("output") is not None:
                    grades = grade_output(suite, case, env_obj["output"], meta, None)
                payload["grades"] = {k: g.to_dict() for k, g in grades.items()}
                judge_usage = empty_usage()
                judge_model = None
                for g in grades.values():
                    if g.judge_usage:
                        add_usage(judge_usage, g.judge_usage)
                        judge_model = g.judge_model
                payload["judge_model"] = judge_model
                payload["judge_usage"] = judge_usage if judge_model else None
                payload["judge_cost_usd"] = cost_usd(judge_model, judge_usage) if judge_model else None
                (traj_dir / f"{case['id']}-r{rep}.json").write_text(
                    json.dumps({"case": case, "envelope": env_obj, "row": payload}, ensure_ascii=False, indent=2), encoding="utf-8",
                )
            return kind, payload

        with ThreadPoolExecutor(max_workers=max(1, opts.concurrency)) as pool:
            futures = {pool.submit(work, j): j for j in jobs}
            for fut in as_completed(futures):
                kind, payload = fut.result()
                (rows if kind == "row" else errors).append(payload)
                mark = {"ok": "✓", "truncated": "✂", "refusal": "⛔"}.get(payload.get("status"), "✗")
                detail = payload.get("failure_class") or " ".join(
                    f"{k}={'-' if v.get('na') else ('P' if v['passed'] else 'F')}"
                    for k, v in (payload.get("grades") or {}).items()
                )
                print(f"  {mark} {payload['case_id']} r{payload['rep']} {detail}", file=sys.stderr)
                _write_jsonl(out_dir / "results.jsonl", rows)
                _write_jsonl(out_dir / "errors.jsonl", errors)

        run_meta["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        suite_metrics = None
        hook = getattr(suite.custom_module, "suite_metrics", None) if suite.custom_module else None
        if callable(hook):
            try:
                suite_metrics = hook([r for r in rows if r["status"] == "ok"])
            except Exception as exc:  # noqa: BLE001
                suite_metrics = {"error": f"{type(exc).__name__}: {exc}"}
        summary = summarize(rows, errors, suite.config, run_meta, suite_metrics)
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "report.md").write_text(render_markdown(summary, rows, errors), encoding="utf-8")
        if opts.update_latest:
            latest = results_root / suite.name / "latest"
            latest.mkdir(parents=True, exist_ok=True)
            for name in ("summary.json", "report.md", "results.jsonl", "errors.jsonl"):
                if (out_dir / name).exists():
                    shutil.copy2(out_dir / name, latest / name)
        shutil.rmtree(workdir, ignore_errors=True)
        return out_dir, summary
