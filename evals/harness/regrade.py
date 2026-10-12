"""Re-score a saved run after a grader change, without calling the model again.

A grader bug found after a paid run should not force a second paid run: every attempt's
input, envelope and grades are in ``trajectories/``, so deterministic metrics can be
recomputed from them. ``llm_rubric`` grades are reused from the saved row (re-judging
would spend money and add judge variance to a comparison that is about the graders).
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .graders import Grade, GradeContext, run_metric
from .pricing import add_usage, cost_usd, empty_usage
from .report import render_markdown, summarize
from .runner import RESULTS_DIR, SkillSuite, _read_jsonl, _write_jsonl


def regrade(suite: SkillSuite, run_dir: Path, update_latest: bool = True) -> tuple[Path, dict]:
    run_dir = Path(run_dir)
    traj_dir = run_dir / "trajectories"
    if not traj_dir.exists():
        raise FileNotFoundError(f"{run_dir} has no trajectories/ to regrade from")
    old_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    errors = _read_jsonl(run_dir / "errors.jsonl")
    cases_by_id = {c["id"]: c for c in suite.cases}
    rows: list[dict] = []
    changed = 0
    for path in sorted(traj_dir.glob("*.json")):
        t = json.loads(path.read_text(encoding="utf-8"))
        case = cases_by_id.get(t["case"]["id"], t["case"])  # current case definition wins
        row = t["row"]
        env = t["envelope"]
        old_grades = row.get("grades") or {}
        new_grades: dict[str, dict] = {}
        if row["status"] in ("ok", "truncated") and env.get("output") is not None:
            ctx = GradeContext(case=case, output=env["output"], meta=env["meta"], judge=None, custom_module=suite.custom_module)
            for m in suite.metrics:
                if m["grader"] == "llm_rubric":
                    if m["name"] in old_grades:
                        new_grades[m["name"]] = old_grades[m["name"]]
                    continue
                new_grades[m["name"]] = run_metric(m, ctx).to_dict()
        for name, g in new_grades.items():
            old = old_grades.get(name)
            if old is None or bool(old.get("passed")) != bool(g.get("passed")) or bool(old.get("na")) != bool(g.get("na")):
                changed += 1
        row["grades"] = new_grades
        judge_usage = empty_usage()
        judge_model = None
        for g in new_grades.values():
            if g.get("judge_usage"):
                add_usage(judge_usage, g["judge_usage"])
                judge_model = g.get("judge_model")
        row["judge_model"] = judge_model
        row["judge_usage"] = judge_usage if judge_model else None
        row["judge_cost_usd"] = cost_usd(judge_model, judge_usage) if judge_model else None
        t["row"] = row
        path.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(row)

    run_meta = dict(old_summary.get("run") or {})
    run_meta["regraded_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    run_meta["regrade_note"] = f"{changed} grade(s) changed; llm_rubric grades reused from the original run"
    suite_metrics = None
    hook = getattr(suite.custom_module, "suite_metrics", None) if suite.custom_module else None
    if callable(hook):
        suite_metrics = hook([r for r in rows if r["status"] == "ok"])
    summary = summarize(rows, errors, suite.config, run_meta, suite_metrics)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(summary, rows, errors), encoding="utf-8")
    _write_jsonl(run_dir / "results.jsonl", rows)
    if update_latest:
        latest = RESULTS_DIR / suite.name / "latest"
        latest.mkdir(parents=True, exist_ok=True)
        for name in ("summary.json", "report.md", "results.jsonl", "errors.jsonl"):
            if (run_dir / name).exists():
                shutil.copy2(run_dir / name, latest / name)
    return run_dir, summary


__all__ = ["regrade", "Grade"]
