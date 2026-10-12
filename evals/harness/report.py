"""Summaries and Markdown reports built from results.jsonl + errors.jsonl rows."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .stats import mean_std, percentile, wilson_interval


def _applicable(row: dict, name: str) -> bool:
    g = row["grades"].get(name)
    return g is not None and not g.get("na")


def summarize(
    rows: list[dict], errors: list[dict], suite_cfg: dict, run_meta: dict, suite_metrics: dict | None = None
) -> dict[str, Any]:
    metric_names = [m["name"] for m in suite_cfg.get("metrics", [])]
    scored = [r for r in rows if r["status"] == "ok"]
    truncated = [r for r in rows if r["status"] == "truncated"]
    refusals = [r for r in rows if r["status"] == "refusal"]

    metrics: dict[str, Any] = {}
    for name in metric_names:
        passes = [bool(r["grades"][name]["passed"]) for r in scored if _applicable(r, name)]
        scores = [float(r["grades"][name]["score"]) for r in scored if _applicable(r, name)]
        n = len(passes)
        k = sum(passes)
        low, high = wilson_interval(k, n)
        m, sd = mean_std(scores)
        metrics[name] = {
            "n": n,
            "passed": k,
            "pass_rate": (k / n) if n else None,
            "ci95": [round(low, 4), round(high, 4)],
            "mean_score": round(m, 4),
            "std_score": round(sd, 4),
        }

    # Per-tag (tags[0]) breakdown so skew is visible.
    by_tag: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        groups[(r.get("tags") or ["untagged"])[0]].append(r)
    for tag, rs in sorted(groups.items()):
        by_tag[tag] = {"n": len(rs)}
        for name in metric_names:
            ps = [bool(r["grades"][name]["passed"]) for r in rs if _applicable(r, name)]
            by_tag[tag][name] = round(sum(ps) / len(ps), 4) if ps else None

    skill_cost = [r.get("cost_usd") for r in rows if r.get("cost_usd") is not None]
    judge_cost = [r.get("judge_cost_usd") for r in rows if r.get("judge_cost_usd") is not None]
    latencies = [float(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None]
    served_models = sorted({r.get("served_model") for r in rows if r.get("served_model")})

    thresholds = suite_cfg.get("thresholds", {}) or {}
    gates = {}
    for name, floor in thresholds.items():
        m = metrics.get(name, {})
        rate = m.get("pass_rate")
        if not m.get("n"):
            # No applicable scored rows (filtered run, or every row was n/a): the gate is not
            # evaluated rather than failed, and the summary says so.
            gates[name] = {"threshold": floor, "pass_rate": None, "n": 0, "passed": None}
        else:
            gates[name] = {"threshold": floor, "pass_rate": rate, "n": m["n"], "passed": rate >= floor}
    infra_error_count = len(errors)
    gate_reasons: list[str] = []
    if not scored:
        gate_reasons.append("no scored attempts")
    if infra_error_count:
        gate_reasons.append(f"{infra_error_count} infrastructure error(s): run is incomplete")
    gate_reasons += [f"{n} below threshold" for n, g in gates.items() if g["passed"] is False]
    gates_skipped = [n for n, g in gates.items() if g["passed"] is None]
    gate_passed = not gate_reasons

    error_classes: dict[str, int] = defaultdict(int)
    for e in errors:
        error_classes[e.get("failure_class", "unknown")] += 1

    return {
        "skill": suite_cfg.get("skill"),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": run_meta,
        "counts": {
            "cases": run_meta.get("cases"),
            "reps": run_meta.get("reps"),
            "attempts": len(rows) + len(errors),
            "scored": len(scored),
            "truncated": len(truncated),
            "refusals": len(refusals),
            "infra_errors": infra_error_count,
            "error_classes": dict(error_classes),
        },
        "refusal_rate": (len(refusals) / len(rows)) if rows else None,
        "metrics": metrics,
        "suite_metrics": suite_metrics or {},
        "by_tag": by_tag,
        "cost": {
            "skill_usd": round(sum(skill_cost), 4) if skill_cost else None,
            "judge_usd": round(sum(judge_cost), 4) if judge_cost else 0.0,
            "per_attempt_usd": round(sum(skill_cost) / len(skill_cost), 4) if skill_cost else None,
            "note": "derived from API-reported tokens and the served model's list price; see harness/pricing.py",
        },
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "mean": round(mean_std(latencies)[0], 1),
            "note": "model-call time only; subprocess start-up, grading and retries excluded",
        },
        "served_models": served_models,
        "gates": gates,
        "gates_skipped": gates_skipped,
        "gate_reasons": gate_reasons,
        "gate_passed": bool(gate_passed),
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def render_markdown(summary: dict, rows: list[dict], errors: list[dict]) -> str:
    s = summary
    c = s["counts"]
    out: list[str] = []
    out.append(f"# Eval report: `{s['skill']}`\n")
    out.append(
        f"Generated {s['generated_at']} · model `{s['run'].get('model')}` · judge `{s['run'].get('judge_model') or 'none'}` · effort `{s['run'].get('effort') or 'script default'}`\n"
    )
    gate_line = f"**Gate:** {'PASS' if s['gate_passed'] else 'FAIL'}"
    if s.get("gate_reasons"):
        gate_line += " (" + "; ".join(s["gate_reasons"]) + ")"
    if s.get("gates_skipped"):
        gate_line += f" · not evaluated (no applicable rows): {', '.join(f'`{n}`' for n in s['gates_skipped'])}"
    out.append(gate_line + "\n")
    out.append("## Counts\n")
    out.append("| cases | reps | attempts | scored | truncated | refusals | infra errors |")
    out.append("|---:|---:|---:|---:|---:|---:|---:|")
    out.append(f"| {c['cases']} | {c['reps']} | {c['attempts']} | {c['scored']} | {c['truncated']} | {c['refusals']} | {c['infra_errors']} |\n")
    if c["error_classes"]:
        out.append("Infrastructure errors by class (not scored as model failures): " + ", ".join(f"`{k}`={v}" for k, v in c["error_classes"].items()) + "\n")
    out.append("## Metrics (scored attempts only)\n")
    out.append("| metric | n | pass rate | 95% CI | mean score | gate |")
    out.append("|---|---:|---:|---|---:|---|")
    for name, m in s["metrics"].items():
        gate = s["gates"].get(name)
        if not gate:
            gate_s = ""
        elif gate["passed"] is None:
            gate_s = f"≥ {_pct(gate['threshold'])} (no rows)"
        else:
            gate_s = f"≥ {_pct(gate['threshold'])} {'✅' if gate['passed'] else '❌'}"
        ci = f"[{_pct(m['ci95'][0])}, {_pct(m['ci95'][1])}]" if m["n"] else "—"
        out.append(f"| `{name}` | {m['n']} | {_pct(m['pass_rate'])} | {ci} | {m['mean_score']:.3f} | {gate_s} |")
    out.append("")
    if s.get("suite_metrics"):
        out.append("## Suite-level statistics\n")
        out.append("| statistic | value |")
        out.append("|---|---|")
        for k, v in s["suite_metrics"].items():
            out.append(f"| `{k}` | {v} |")
        out.append("")
    if s["by_tag"]:
        names = list(s["metrics"].keys())
        out.append("## By stratum (`tags[0]`)\n")
        out.append("| stratum | n | " + " | ".join(f"`{n}`" for n in names) + " |")
        out.append("|---|---:|" + "---:|" * len(names))
        for tag, d in s["by_tag"].items():
            out.append(f"| {tag} | {d['n']} | " + " | ".join(_pct(d.get(n)) for n in names) + " |")
        out.append("")
    out.append("## Cost and latency\n")
    cost = s["cost"]
    lat = s["latency_ms"]
    out.append(f"- Skill cost: **${cost['skill_usd'] if cost['skill_usd'] is not None else 'n/a'}** total, ${cost['per_attempt_usd'] if cost['per_attempt_usd'] is not None else 'n/a'} per attempt")
    out.append(f"- Judge cost (recorded separately): **${cost['judge_usd']}**")
    out.append(f"- Model latency: p50 {lat['p50']:.0f} ms, p95 {lat['p95']:.0f} ms, mean {lat['mean']:.0f} ms ({lat['note']})")
    out.append(f"- Served model(s): {', '.join(f'`{m}`' for m in s['served_models']) or 'n/a'}")
    out.append(f"- Refusal rate: {_pct(s['refusal_rate'])}\n")
    out.append("## Per-attempt results\n")
    names = list(s["metrics"].keys())
    out.append("| case | rep | status | " + " | ".join(f"`{n}`" for n in names) + " | cost | ms |")
    out.append("|---|---:|---|" + "---|" * len(names) + "---:|---:|")
    for r in sorted(rows, key=lambda r: (r["case_id"], r["rep"])):
        cells = []
        for n in names:
            g = r["grades"].get(n)
            cells.append("—" if g is None else ("n/a" if g.get("na") else ("✅" if g["passed"] else "❌")))
        cost_s = f"{r['cost_usd']:.4f}" if r.get("cost_usd") is not None else "n/a"
        out.append(f"| {r['case_id']} | {r['rep']} | {r['status']} | " + " | ".join(cells) + f" | {cost_s} | {r.get('latency_ms', 0)} |")
    out.append("")
    failed = [(r, n) for r in rows if r["status"] == "ok" for n in names if _applicable(r, n) and not r["grades"][n]["passed"]]
    if failed:
        out.append("## Failure evidence\n")
        for r, n in failed[:60]:
            ev = str(r["grades"][n]["evidence"]).replace("\n", " ")[:300]
            out.append(f"- `{r['case_id']}` r{r['rep']} `{n}`: {ev}")
        out.append("")
    if errors:
        out.append("## Infrastructure errors\n")
        for e in errors[:40]:
            msg = str(e.get("message", "")).replace("\n", " ")[:200]
            out.append(f"- `{e['case_id']}` r{e['rep']} **{e['failure_class']}**: {msg}")
        out.append("")
    return "\n".join(out)
