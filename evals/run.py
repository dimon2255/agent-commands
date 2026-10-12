"""CLI for the API-level eval suite.

    uv run evals/run.py --skill extract                # one skill, 1 rep
    uv run evals/run.py --all --reps 2 --concurrency 4 # everything
    uv run evals/run.py --skill judge --smoke           # oracle + null baseline, no API
    uv run evals/run.py --skill adr --case "adr-*cache*" --limit 2

Exit code 0 when every selected suite passes its gates, 1 otherwise, 2 on usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.harness.runner import (  # noqa: E402
    REPO_ROOT,
    Runner,
    RunOptions,
    discover_suites,
    load_suite,
    smoke,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--skill", action="append", help="skill name (repeatable)")
    p.add_argument("--all", action="store_true", help="run every skill that has evals/config.yaml")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--effort", default=None, help="low|medium|high|xhigh|max (script default when omitted)")
    p.add_argument("--judge-model", default="claude-opus-5-5")
    p.add_argument("--no-judge", action="store_true", help="skip llm_rubric metrics (they report as GRADER ERROR)")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--case", default=None, help="glob on case id")
    p.add_argument("--tag", default=None)
    p.add_argument("--allow-model-mismatch", action="store_true")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--resume", default=None, help="existing run directory to continue")
    p.add_argument("--no-latest", action="store_true", help="do not copy this run into results/api/<skill>/latest (comparison runs)")
    p.add_argument("--smoke", action="store_true", help="oracle + null baseline through graders; no API calls")
    p.add_argument("--list", action="store_true", help="list suites and cases, then exit")
    args = p.parse_args(argv)

    if args.all:
        suites = discover_suites(REPO_ROOT)
    elif args.skill:
        suites = [load_suite(REPO_ROOT / "skills" / s) for s in args.skill]
    else:
        p.error("pass --skill <name> or --all")
        return 2

    if args.list:
        for s in suites:
            print(f"{s.name}: {len(s.cases)} cases, metrics {[m['name'] for m in s.metrics]}")
            for c in s.cases:
                print(f"  - {c['id']} tags={c.get('tags')}")
        return 0

    if args.smoke:
        ok = True
        for s in suites:
            res = smoke(s)
            ok = ok and res["ok"]
            print(json.dumps(res, indent=2))
        return 0 if ok else 1

    judge = None
    if not args.no_judge and any(m["grader"] == "llm_rubric" for s in suites for m in s.metrics):
        from evals.harness.llm import Judge

        judge = Judge(model=args.judge_model)

    opts = RunOptions(
        model=args.model, effort=args.effort, judge_model=args.judge_model, reps=args.reps,
        concurrency=args.concurrency, limit=args.limit, case_filter=args.case, tag_filter=args.tag,
        allow_model_mismatch=args.allow_model_mismatch,
        out_dir=Path(args.out_dir) if args.out_dir else None,
        resume=Path(args.resume) if args.resume else None,
        update_latest=not args.no_latest,
    )
    all_ok = True
    for s in suites:
        out_dir, summary = Runner(s, opts, judge=judge).run()
        all_ok = all_ok and summary["gate_passed"]
        print(f"\n[{s.name}] gate {'PASS' if summary['gate_passed'] else 'FAIL'} -> {out_dir / 'report.md'}")
        for name, m in summary["metrics"].items():
            rate = "n/a" if m["pass_rate"] is None else f"{100 * m['pass_rate']:.1f}%"
            print(f"   {name:<28} {rate:>7}  n={m['n']}  ci95=[{100 * m['ci95'][0]:.0f}%, {100 * m['ci95'][1]:.0f}%]")
        c = summary["counts"]
        print(f"   scored={c['scored']} truncated={c['truncated']} refusals={c['refusals']} infra_errors={c['infra_errors']}  cost=${summary['cost']['skill_usd']} (+judge ${summary['cost']['judge_usd']})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
