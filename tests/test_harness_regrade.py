import json
from pathlib import Path

from evals.harness.regrade import regrade
from evals.harness.runner import Runner, RunOptions, load_suite

FIXTURE = Path(__file__).parent / "fixtures" / "fakeskill"


def test_regrade_reproduces_then_reflects_a_grader_change(tmp_path):
    s = load_suite(FIXTURE)
    opts = RunOptions(model="fake-model", reps=1, concurrency=2, results_root=tmp_path, out_dir=tmp_path / "run", case_filter="ok-*")
    out_dir, first = Runner(s, opts).run()
    assert first["metrics"]["answer_exact"]["passed"] == 1

    # Same graders -> same numbers, nothing changed.
    _, again = regrade(s, out_dir, update_latest=False)
    assert again["metrics"]["answer_exact"]["passed"] == 1
    assert again["run"]["regrade_note"].startswith("0 grade(s) changed")

    # A changed expectation (as if a label or grader bug were fixed) is reflected without a rerun.
    for c in s.cases:
        if c["id"] == "ok-mismatch":
            c["expected"]["answer"] = "Lyon"
    _, fixed = regrade(s, out_dir, update_latest=False)
    assert fixed["metrics"]["answer_exact"]["passed"] == 2
    assert fixed["run"]["regrade_note"].startswith("1 grade(s) changed")
    rows = [json.loads(line) for line in (out_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(r["grades"]["answer_exact"]["passed"] for r in rows)
    assert (out_dir / "report.md").read_text(encoding="utf-8").startswith("# Eval report")
