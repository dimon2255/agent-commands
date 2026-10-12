from evals.harness.graders import GradeContext, normalize, run_metric


def ctx(output, case=None, meta=None):
    return GradeContext(case=case or {"input": {}, "expected": {}}, output=output, meta=meta or {})


def test_normalize_is_lenient_but_not_sloppy():
    assert normalize(" Paris ") == normalize("paris")
    assert normalize(4) == normalize("4.0") == normalize("$4")
    assert normalize("1,234.50") == normalize(1234.5)
    assert normalize(True) == "true"
    assert normalize("paris") != normalize("lyon")
    assert normalize(None) == ""


def test_exact_grader_resolves_refs():
    c = {"input": {}, "expected": {"total": "1,234.00"}}
    g = run_metric({"name": "t", "grader": "exact", "target": "$output.total", "expected": "$expected.total"}, ctx({"total": 1234}, c))
    assert g.passed and g.score == 1.0


def test_exact_grader_fails_on_difference():
    c = {"input": {}, "expected": {"total": 10}}
    g = run_metric({"name": "t", "grader": "exact", "target": "$output.total", "expected": "$expected.total"}, ctx({"total": 11}, c))
    assert not g.passed and "expected" in g.evidence


def test_missing_ref_is_a_failed_grade_not_a_crash():
    g = run_metric({"name": "t", "grader": "exact", "target": "$output.nope", "expected": "x"}, ctx({"total": 1}))
    assert not g.passed and "GRADER ERROR" in g.evidence


def test_json_schema_grader():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"], "additionalProperties": False}
    ok = run_metric({"name": "s", "grader": "json_schema", "target": "$output", "schema": schema}, ctx({"a": 1}))
    bad = run_metric({"name": "s", "grader": "json_schema", "target": "$output", "schema": schema}, ctx({"a": "x"}))
    assert ok.passed and not bad.passed and "schema error" in bad.evidence


def test_json_schema_grader_enforces_formats():
    schema = {"type": "object", "properties": {"d": {"type": "string", "format": "date"}}, "required": ["d"]}
    ok = run_metric({"name": "s", "grader": "json_schema", "target": "$output", "schema": schema}, ctx({"d": "2026-03-03"}))
    bad = run_metric({"name": "s", "grader": "json_schema", "target": "$output", "schema": schema}, ctx({"d": "March 3rd, 2026"}))
    assert ok.passed and not bad.passed and "date" in bad.evidence


def test_regex_and_contains_and_not_contains():
    out = {"text": "Decision: use Redis\nStatus: Accepted"}
    assert run_metric({"name": "r", "grader": "regex", "target": "$output.text", "pattern": "^status: accepted$", "flags": "im"}, ctx(out)).passed
    assert run_metric({"name": "c", "grader": "contains", "target": "$output.text", "needle": "use redis"}, ctx(out)).passed
    assert run_metric({"name": "n", "grader": "regex", "target": "$output.text", "pattern": "TBD", "match": "not_contains"}, ctx(out)).passed
    assert not run_metric({"name": "c", "grader": "contains", "target": "$output.text", "needle": ""}, ctx(out)).passed


def test_paths_subset_scores_partially():
    out = {"paths": ["src/a.py", "src\\b.py", "src/zzz.py"]}
    g = run_metric({"name": "p", "grader": "paths_subset", "target": "$output.paths", "allowed": ["src/a.py", "src/b.py"]}, ctx(out))
    assert not g.passed and abs(g.score - 2 / 3) < 1e-9 and "zzz" in g.evidence
    empty = run_metric({"name": "p", "grader": "paths_subset", "target": "$output.none", "allowed": []}, ctx({"none": []}))
    assert empty.passed
    # leading ./ is stripped; dot-directories and parent references are preserved
    dotted = run_metric(
        {"name": "p", "grader": "paths_subset", "target": "$output.paths", "allowed": [".github/ci.yml", "../x.py"]},
        ctx({"paths": ["./.github/ci.yml", "../x.py"]}),
    )
    assert dotted.passed, dotted.evidence
    parent = run_metric({"name": "p", "grader": "paths_subset", "target": "$output.paths", "allowed": ["x.py"]}, ctx({"paths": ["../x.py"]}))
    assert not parent.passed


def test_unknown_grader_raises():
    import pytest

    with pytest.raises(RuntimeError):
        run_metric({"name": "x", "grader": "nope"}, ctx({}))


def test_llm_rubric_without_judge_is_failed_grade():
    g = run_metric({"name": "j", "grader": "llm_rubric", "rubric": "r", "target": "$output"}, ctx({"x": 1}))
    assert not g.passed and "GRADER ERROR" in g.evidence
