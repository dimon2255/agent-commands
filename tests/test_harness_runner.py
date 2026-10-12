from pathlib import Path

from evals.harness.contract import validate_envelope
from evals.harness.runner import Runner, RunOptions, load_suite, smoke

FIXTURE = Path(__file__).parent / "fixtures" / "fakeskill"


def test_load_suite_reads_config_cases_and_graders():
    s = load_suite(FIXTURE)
    assert s.name == "fakeskill" and len(s.cases) == 8
    assert [m["name"] for m in s.metrics] == ["answer_exact", "schema_valid", "custom_len"]
    assert s.custom_module is not None


def test_smoke_oracle_passes_and_null_fails():
    s = load_suite(FIXTURE)
    res = smoke(s)
    assert res["ok"], res
    assert res["null_baseline_passes"] == []


def test_validate_envelope_reports_problems():
    assert validate_envelope("nope") == ["envelope is not a JSON object"]
    probs = validate_envelope({"ok": True, "output": None, "error": None, "meta": {"status": "weird"}})
    assert any("status" in p for p in probs) and any("output is null" in p for p in probs)


def test_runner_classifies_every_attempt(tmp_path):
    s = load_suite(FIXTURE)
    opts = RunOptions(model="fake-model", reps=1, concurrency=3, results_root=tmp_path, out_dir=tmp_path / "run")
    out_dir, summary = Runner(s, opts, judge=None).run()

    c = summary["counts"]
    # 8 attempts: ok-match, ok-mismatch (scored), truncated, refusal (rows), api-error, crash, garbage, wrong-model (errors)
    assert c["attempts"] == 8
    assert c["scored"] == 2 and c["truncated"] == 1 and c["refusals"] == 1 and c["infra_errors"] == 4
    assert set(c["error_classes"]) == {"api_error", "crash", "unparseable_stdout", "served_model_mismatch"}

    m = summary["metrics"]["answer_exact"]
    assert m["n"] == 2 and m["passed"] == 1 and m["pass_rate"] == 0.5
    assert m["ci95"][0] < 0.5 < m["ci95"][1]
    assert summary["gates"]["answer_exact"]["passed"] is True
    assert summary["by_tag"]["happy"]["n"] == 2
    assert summary["refusal_rate"] == 0.25  # 1 of 4 rows

    assert (out_dir / "results.jsonl").exists() and (out_dir / "errors.jsonl").exists()
    assert (out_dir / "report.md").read_text(encoding="utf-8").startswith("# Eval report: `fakeskill`")
    assert (tmp_path / "fakeskill" / "latest" / "summary.json").exists()
    assert len(list((out_dir / "trajectories").glob("*.json"))) == 4


def test_runner_resume_skips_done_attempts(tmp_path):
    s = load_suite(FIXTURE)
    opts = RunOptions(model="fake-model", reps=1, concurrency=2, results_root=tmp_path, out_dir=tmp_path / "run", case_filter="ok-*")
    out_dir, summary = Runner(s, opts).run()
    assert summary["counts"]["attempts"] == 2
    opts2 = RunOptions(model="fake-model", reps=2, concurrency=2, results_root=tmp_path, resume=out_dir, case_filter="ok-*")
    _, summary2 = Runner(s, opts2).run()
    assert summary2["counts"]["attempts"] == 4
    assert summary2["metrics"]["answer_exact"]["n"] == 4
