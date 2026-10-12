from pathlib import Path

from evals.harness.contract import validate_envelope
from evals.harness.report import summarize
from evals.harness.runner import Runner, RunOptions, load_suite, smoke, validate_config

FIXTURE = Path(__file__).parent / "fixtures" / "fakeskill"


def test_load_suite_reads_config_cases_and_graders():
    s = load_suite(FIXTURE)
    assert s.name == "fakeskill" and len(s.cases) == 8
    assert [m["name"] for m in s.metrics] == ["answer_exact", "schema_valid", "custom_len", "edge_only"]
    assert s.custom_module is not None


def test_smoke_oracle_passes_and_null_fails_and_na_is_ignored():
    s = load_suite(FIXTURE)
    res = smoke(s)
    assert res["ok"], res
    assert res["null_baseline_passes"] == [] and res["null_unfalsifiable"] == []


def test_smoke_flags_a_null_output_that_passes(tmp_path):
    s = load_suite(FIXTURE)
    s.config["null_output"] = {"answer": "paris"}  # passes answer_exact for ok-match
    res = smoke(s)
    assert not res["ok"] and "ok-match" in res["null_baseline_passes"]


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
    assert c["grader_errors"] == 0

    m = summary["metrics"]["answer_exact"]
    assert m["n"] == 2 and m["passed"] == 1 and m["pass_rate"] == 0.5
    assert m["ci95"][0] < 0.5 < m["ci95"][1]
    assert summary["gates"]["answer_exact"]["passed"] is True
    # edge_only is n/a on both scored (happy) rows -> gate not evaluated, not failed
    assert summary["metrics"]["edge_only"]["n"] == 0
    assert summary["gates"]["edge_only"]["passed"] is None and summary["gates_skipped"] == ["edge_only"]
    # infra errors make the run incomplete, so the overall gate fails with a stated reason
    assert summary["gate_passed"] is False and any("infrastructure" in r for r in summary["gate_reasons"])
    assert summary["suite_metrics"] == {"scored_rows": 2}
    assert summary["by_tag"]["happy"]["n"] == 2
    assert summary["refusal_rate"] == 0.25  # 1 of 4 rows

    assert (out_dir / "results.jsonl").exists() and (out_dir / "errors.jsonl").exists()
    assert (out_dir / "report.md").read_text(encoding="utf-8").startswith("# Eval report: `fakeskill`")
    assert (tmp_path / "fakeskill" / "latest" / "summary.json").exists()
    assert len(list((out_dir / "trajectories").glob("*.json"))) == 4


def test_validate_config_rejects_unknown_threshold_and_duplicates():
    base = {"skill": "x", "entrypoint": "s.py", "cases": "c.jsonl", "metrics": [{"name": "a", "grader": "exact"}]}
    assert validate_config(base) == []
    assert any("unknown metric" in p for p in validate_config({**base, "thresholds": {"typo": 0.5}}))
    assert any("duplicate" in p for p in validate_config({**base, "metrics": [{"name": "a"}, {"name": "a"}]}))
    assert any("missing" in p for p in validate_config({"skill": "x"}))


def test_summarize_keeps_grader_errors_out_of_pass_rates_but_fails_the_gate():
    cfg = {"skill": "x", "metrics": [{"name": "m", "grader": "exact"}], "thresholds": {"m": 0.5}}
    rows = [
        {"case_id": "a", "rep": 1, "tags": ["t"], "status": "ok", "grades": {"m": {"score": 1, "passed": True, "evidence": ""}}},
        {"case_id": "b", "rep": 1, "tags": ["t"], "status": "ok", "grades": {"m": {"score": 0, "passed": False, "evidence": "JUDGE ERROR", "error": True}}},
    ]
    s = summarize(rows, [], cfg, {"cases": 2, "reps": 1})
    assert s["metrics"]["m"]["n"] == 1 and s["metrics"]["m"]["pass_rate"] == 1.0
    assert s["metrics"]["m"]["grader_errors"] == 1 and s["counts"]["grader_errors"] == 1
    assert s["gate_passed"] is False and any("grader error" in r for r in s["gate_reasons"])


def test_resume_retries_errored_attempts_and_drops_their_old_error_rows(tmp_path):
    s = load_suite(FIXTURE)
    opts = RunOptions(model="fake-model", reps=1, concurrency=2, results_root=tmp_path, out_dir=tmp_path / "run", case_filter="crash")
    out_dir, first = Runner(s, opts).run()
    assert first["counts"]["infra_errors"] == 1 and first["gate_passed"] is False
    for c in s.cases:  # the transient failure is gone on the retry
        if c["id"] == "crash":
            c["input"] = {"echo": {"answer": "x"}, "schema": {"type": "object"}}
    opts2 = RunOptions(model="fake-model", reps=1, concurrency=2, results_root=tmp_path, resume=out_dir, case_filter="crash")
    _, second = Runner(s, opts2).run()
    assert second["counts"]["attempts"] == 1 and second["counts"]["infra_errors"] == 0
    assert second["gate_passed"] is True


def test_runner_resume_skips_done_attempts(tmp_path):
    s = load_suite(FIXTURE)
    opts = RunOptions(model="fake-model", reps=1, concurrency=2, results_root=tmp_path, out_dir=tmp_path / "run", case_filter="ok-*")
    out_dir, summary = Runner(s, opts).run()
    assert summary["counts"]["attempts"] == 2
    opts2 = RunOptions(model="fake-model", reps=2, concurrency=2, results_root=tmp_path, resume=out_dir, case_filter="ok-*")
    _, summary2 = Runner(s, opts2).run()
    assert summary2["counts"]["attempts"] == 4
    assert summary2["metrics"]["answer_exact"]["n"] == 4
    assert summary2["gate_passed"] is True and summary2["gate_reasons"] == []
