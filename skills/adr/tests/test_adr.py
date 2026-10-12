"""Unit tests for the adr skill: script pipeline, path check, graders and suite wiring.

No network and no API key: model calls go through a fake client with the SDK's shape.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from evals.harness.contract import validate_envelope
from evals.harness.graders import GradeContext, run_metric
from evals.harness.runner import load_suite, smoke

SKILL_DIR = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


adr = _load("adr_script_under_test", SKILL_DIR / "scripts" / "adr.py")
graders = _load("adr_graders_under_test", SKILL_DIR / "evals" / "graders.py")
CASES = {c["id"]: c for c in map(json.loads, (SKILL_DIR / "evals" / "cases.jsonl").read_text(encoding="utf-8").splitlines())}
DECOY = CASES["adr-tricky-cache-decoy-010"]


# --------------------------------------------------------------------------- fakes


def fake_response(draft: dict | None = None, *, stop_reason: str = "end_turn", model: str = "claude-opus-5-5",
                  stop_details: object = None) -> SimpleNamespace:
    content = [SimpleNamespace(type="text", text=json.dumps(draft))] if draft is not None else []
    usage = SimpleNamespace(input_tokens=1500, output_tokens=900, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=content, model=model, stop_reason=stop_reason, usage=usage,
                           stop_details=stop_details, _request_id="req_test")


class FakeClient:
    def __init__(self, *responses: object) -> None:
        self.requests: list[dict] = []
        self._responses = list(responses)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def make_draft(markdown: str, *, listed: list[str] | None = None, alternatives: int = 2,
               negatives: list[str] | None = None) -> dict:
    return {
        "title": "Two-level catalogue cache",
        "slug": "Two-Level Catalogue Cache!",
        "markdown": markdown,
        "alternatives": [{"name": f"Option {i}", "rejected_because": "reason"} for i in range(alternatives)],
        "consequences": {"positive": ["Fresh prices."], "negative": negatives if negatives is not None else ["Redis becomes a dependency."]},
        "referenced_paths": listed if listed is not None else [],
    }


GOOD_MD = """# ADR 001: Two-level catalogue cache

**Status:** Proposed, 2026-10-12

## Context

`src/cache.py` caches per process; the stale notes mention `src/caching.py`.

## Decision

Use Redis behind a 4-second local cache.

## Alternatives considered

- Option 0: reason
- Option 1: reason

## Consequences

Positive:

- Fresh prices.

Negative:

- Redis becomes a dependency.
"""


# --------------------------------------------------------------------------- numbering


def test_next_number_uses_highest_existing_and_ignores_bad_entries():
    assert adr.next_number([]) == 1
    assert adr.next_number([{"number": n} for n in (1, 2, 3)]) == 4
    assert adr.next_number([{"number": 7}, {"number": "2"}, {"title": "no number"}, {"number": "x"}]) == 8


def test_scan_adr_dir_reads_numbers_and_titles(tmp_path):
    (tmp_path / "001-first.md").write_text("# ADR 001: First thing\n\nbody\n", encoding="utf-8")
    (tmp_path / "002-second-thing.md").write_text("no heading here\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# Not an ADR\n", encoding="utf-8")
    (tmp_path / "003-draft.txt").write_text("# ADR 003: wrong extension\n", encoding="utf-8")
    found = adr.scan_adr_dir(tmp_path)
    assert found == [{"number": 1, "title": "First thing"}, {"number": 2, "title": "second thing"}]
    assert adr.next_number(found) == 3
    assert adr.scan_adr_dir(tmp_path / "missing") == []


# --------------------------------------------------------------------------- path check

PACK = ["src/cache.py", "src/catalog.py", "config/settings.toml", "docs/architecture.md"]


@pytest.mark.parametrize(
    ("markdown", "referenced", "unknown"),
    [
        ("See `src\\cache.py` and `config\\settings.toml`.", ["src/cache.py", "config/settings.toml"], []),
        ("The notes cite `src/caching.py`, which does not exist.", [], ["src/caching.py"]),
        ("```python\nfrom x import y  # defined in src/catalog.py\n```", ["src/catalog.py"], []),
        ("Edit `cache.py` and `./src/catalog.py`.", ["src/cache.py", "src/catalog.py"], []),
        ("Move it to `settings.py` under `src/workers/`.", [], ["settings.py", "src/workers"]),
        ("Everything in `src/` and `docs/` stays.", ["src", "docs"], []),
        ("read/write, application/json, /v2/orders, https://example.com/a.md, Node.js, "
         "process.env.API_KEY, redis://cache:6379/0, @nestjs/common, TCP/IP.", [], []),
        ("Ends a sentence with docs/architecture.md. Then src/cache.py's TTL.",
         ["docs/architecture.md", "src/cache.py"], []),
        # Object-key templates, placeholders and glob suffixes are not repository paths ...
        ("Key `invoices/{invoice_id}/{sha256}.pdf`, `<adr-dir>/NNN.md`, `${HOME}/x.py`, `docs/*.md`.",
         ["docs"], []),
        # ... but Markdown emphasis around a real citation is still checked.
        ("*src/caching.py* and **src/cache.py**", ["src/cache.py"], ["src/caching.py"]),
        # Code identifiers that end like an extension are not files.
        ("`res.json(...)`, `response.json()`, `threading.Lock`, `process.env`, `import.meta.env`.", [], []),
        # Paths inside URLs and package scopes are skipped by both implementations alike.
        ("`http://localhost:8080/openapi.yaml` and `@acme/eslint-config/index.js`", [], []),
        ("New files `infra/prod.tfvars` and `vitest.config.mts`.", [], ["infra/prod.tfvars", "vitest.config.mts"]),
    ],
)
def test_check_paths_and_grader_agree(markdown, referenced, unknown):
    got = adr.check_paths(markdown, [], PACK)
    assert got == {"referenced": referenced, "unknown": unknown}
    grounded, g_unknown = graders.classify_markdown_paths(markdown, PACK)
    assert g_unknown == unknown  # independent implementation, same verdict
    assert bool(grounded) == bool(referenced)


def test_check_paths_flags_paths_only_the_model_listed():
    got = adr.check_paths("No paths in the prose.", ["src/workers", "src/cache.py"], PACK)
    assert got == {"referenced": ["src/cache.py"], "unknown": ["src/workers"]}


# --------------------------------------------------------------------------- post-checks


def test_post_checks_warn_on_structure_placeholders_and_phantom_paths():
    md = "# ADR 002: X\n\n## Context\n\nTBD, see `src/cache.py`.\n\n## Alternatives considered\n\n- A: no\n"
    out = adr.finalize(make_draft(md, listed=["config/settings.toml"], alternatives=1, negatives=[]), 2, PACK)
    w = " | ".join(out["warnings"])
    for expected in ("missing section '## Decision'", "missing section '## Consequences'", "1 alternative(s)",
                     "no negative consequence", "placeholder text 'TBD'",
                     "referenced_paths lists paths the markdown does not cite: config/settings.toml"):
        assert expected in w
    assert out["slug"] == "two-level-catalogue-cache"


def test_title_without_separator_warns_and_slugs_keep_six_whole_words():
    out = adr.finalize(make_draft(GOOD_MD.replace("# ADR 001: Two", "# ADR 001 Two"), listed=["src/cache.py"]), 1, PACK)
    assert "missing title heading '# ADR NNN: ...'" in out["warnings"]
    assert adr.slugify("Two-level catalogue cache with a shared Redis layer!") == "two-level-catalogue-cache-with-a"
    assert adr.slugify("!!!") == "decision"


def test_finalize_is_clean_for_a_good_draft_and_corrects_the_heading_number():
    md = GOOD_MD.replace("ADR 001", "ADR 007").replace("; the stale notes mention `src/caching.py`", "")
    out = adr.finalize(make_draft(md, listed=["src/cache.py"]), 1, PACK)
    assert out["markdown"].startswith("# ADR 001: ")
    assert out["warnings"] == ["heading said ADR 007; corrected to 001"]
    assert out["path_check"] == {"referenced": ["src/cache.py"], "unknown": []}


# --------------------------------------------------------------------------- context loader


def test_load_context_skips_binary_large_secret_and_vendored_files(tmp_path):
    (tmp_path / "app.py").write_bytes(b"print('hi')\n")  # bytes: the loader must return them verbatim
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    (tmp_path / "huge.txt").write_text("x" * (adr.MAX_CONTEXT_BYTES + 1), encoding="utf-8")
    (tmp_path / "latin1.txt").write_bytes("caf\xe9".encode("latin-1"))
    (tmp_path / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("module.exports = 1\n", encoding="utf-8")

    pack, skipped = adr.load_context([str(tmp_path), str(tmp_path / "nope.py")], base=tmp_path)
    assert [f["path"] for f in pack] == ["app.py", "sub/notes.md"]
    assert pack[0]["content"] == "print('hi')\n"
    skipped_names = " ".join(skipped)
    for name in ("logo.png", "huge.txt", "latin1.txt", ".env", "nope.py (not found)"):
        assert name in skipped_names
    assert "dep.js" not in skipped_names  # vendored directories are pruned, not reported file by file


# --------------------------------------------------------------------------- pipeline


def test_pipeline_produces_valid_envelope_and_python_path_check_overrides_the_model():
    # The model claims it only cited src/cache.py; its markdown also cites the decoy.
    client = FakeClient(fake_response(make_draft(GOOD_MD, listed=["src/cache.py"])))
    tracker = adr.Tracker("claude-opus-5-5")
    out = adr.draft_adr(client, tracker, DECOY["input"], model="claude-opus-5-5", effort="high", date="2026-10-12")
    env = tracker.envelope(out)

    assert validate_envelope(env) == [] and env["ok"] is True
    assert env["meta"]["status"] == "ok" and env["meta"]["served_model"] == "claude-opus-5-5"
    assert env["meta"]["calls"][0]["purpose"] == "draft"
    assert env["meta"]["usage"]["input_tokens"] == 1500
    assert out["number"] == DECOY["expected"]["number"] == 1
    assert out["referenced_paths"] == ["src/cache.py"]  # the model's claim is kept, not trusted
    assert out["path_check"] == {"referenced": ["src/cache.py"], "unknown": ["src/caching.py"]}
    assert any("not in the context pack: src/caching.py" in w for w in out["warnings"])

    req = client.requests[0]
    assert "thinking" not in req and "temperature" not in req
    assert req["max_tokens"] >= 12000 and req["model"] == "claude-opus-5-5"
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    user = req["messages"][0]["content"]
    assert "<allowed_paths>\nsrc/cache.py\nsrc/catalog.py" in user and "date 2026-10-12" in user
    assert user.rstrip().endswith("return the JSON object.")


def test_refusal_becomes_refusal_status_without_output():
    details = SimpleNamespace(category="cyber", explanation="declined")
    client = FakeClient(fake_response(None, stop_reason="refusal", stop_details=details))
    tracker = adr.Tracker("claude-opus-5-5")
    out = adr.draft_adr(client, tracker, DECOY["input"], model="claude-opus-5-5", effort="high", date="2026-10-12")
    env = tracker.envelope(out)
    assert validate_envelope(env) == []
    assert env["meta"]["status"] == "refusal" and env["ok"] is False and env["output"] is None
    assert env["error"] == {"type": "refusal", "category": "cyber", "message": "declined"}


def test_truncation_becomes_truncated_status():
    client = FakeClient(fake_response(None, stop_reason="max_tokens"))
    tracker = adr.Tracker("claude-opus-5-5")
    env = tracker.envelope(adr.draft_adr(client, tracker, DECOY["input"], model="claude-opus-5-5",
                                         effort="high", date="2026-10-12"))
    assert env["meta"]["status"] == "truncated" and env["ok"] is False and validate_envelope(env) == []


def _write_input(tmp_path: Path) -> str:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(DECOY["input"]), encoding="utf-8")
    return str(path)


def test_main_json_mode_prints_only_the_envelope(tmp_path, capsys):
    client = FakeClient(fake_response(make_draft(GOOD_MD, listed=["src/cache.py"])))
    assert adr.main(["--input", _write_input(tmp_path), "--json"], client=client) == 0
    env = json.loads(capsys.readouterr().out)
    assert validate_envelope(env) == [] and env["ok"] is True and env["output"]["number"] == 1


def test_main_api_error_and_missing_key_still_emit_an_envelope(tmp_path, capsys, monkeypatch):
    inp = _write_input(tmp_path)
    assert adr.main(["--input", inp, "--json"], client=FakeClient(RuntimeError("overloaded"))) == 0
    env = json.loads(capsys.readouterr().out)
    assert env["meta"]["status"] == "error" and env["error"]["type"] == "RuntimeError"

    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert adr.main(["--input", inp, "--json"]) == 0
    env = json.loads(capsys.readouterr().out)
    assert env["meta"]["status"] == "error" and "CLAUDE_API_KEY" in env["error"]["message"]
    assert validate_envelope(env) == []


def test_json_mode_survives_a_failed_write(tmp_path, capsys):
    (tmp_path / "blocker").write_text("a file where the ADR directory should be", encoding="utf-8")
    clean = GOOD_MD.replace("; the stale notes mention `src/caching.py`", "")
    argv = ["--input", _write_input(tmp_path), "--json", "--write", "--adr-dir", str(tmp_path / "blocker" / "adr")]
    assert adr.main(argv, client=FakeClient(fake_response(make_draft(clean, listed=["src/cache.py"])))) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["ok"] is True and "not written" in captured.err


def test_human_cli_writes_clean_records_and_refuses_ungrounded_ones(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "cache.py").write_text("CACHE = {}\n", encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "001-first.md").write_text("# ADR 001: First\n", encoding="utf-8")
    argv = ["--decision", "Should the cache be shared?", "--context", "src", "--adr-dir", "docs/adr",
            "--write", "--date", "2026-10-12"]

    clean = GOOD_MD.replace("; the stale notes mention `src/caching.py`", "")
    assert adr.main(argv, client=FakeClient(fake_response(make_draft(clean, listed=["src/cache.py"])))) == 0
    written = tmp_path / "docs" / "adr" / "002-two-level-catalogue-cache.md"
    assert written.read_text(encoding="utf-8").startswith("# ADR 002: Two-level catalogue cache")
    assert "cited paths:   src/cache.py" in capsys.readouterr().out

    written.unlink()
    assert adr.main(argv, client=FakeClient(fake_response(make_draft(GOOD_MD)))) == 1
    assert not written.exists()
    assert "not written" in capsys.readouterr().err


# --------------------------------------------------------------------------- graders


def _gold(case: dict) -> dict:
    return json.loads(json.dumps(case["expected"]["gold_output"]))


def test_structure_graders_pass_gold_and_fail_broken_records():
    case = CASES["adr-storage-session-001"]
    gold = _gold(case)
    for fn in (graders.sections_present, graders.two_plus_alternatives, graders.negative_consequence_present):
        assert fn(case, gold, {})["passed"], fn.__name__

    broken = dict(gold, markdown=gold["markdown"].replace("## Decision", "## The decision"))
    assert graders.sections_present(case, broken, {})["evidence"].startswith("missing: Decision; words=")

    head = gold["markdown"].split("## Alternatives considered")[0] + "## Alternatives considered\n\n"
    tail = "\n## Consequences\n\nNegative:\n\n- x\n"
    for body in ("- Only one: no\n", "### Redis\n\n- fast\n- but new infrastructure\n"):
        res = graders.two_plus_alternatives(case, dict(gold, markdown=head + body + tail), {})
        assert not res["passed"] and res["evidence"] == "alternatives=3 markdown_items=1", body
    two_h3 = "### Redis\n\n- new infrastructure\n\n### Sticky sessions\n\n- lost on deploy\n"
    assert graders.two_plus_alternatives(case, dict(gold, markdown=head + two_h3 + tail), {})["passed"]

    hidden = dict(gold, consequences={"positive": [], "negative": ["A negative that the markdown never mentions at all"]})
    assert not graders.negative_consequence_present(case, hidden, {})["passed"]
    assert not graders.negative_consequence_present(case, dict(gold, consequences={"positive": [], "negative": [" "]}), {})["passed"]


def test_paths_grounded_reports_unknown_paths_and_requires_a_citation():
    gold = _gold(DECOY)
    assert graders.paths_grounded(DECOY, gold, {}) == {"score": 1.0, "passed": True, "evidence": "paths=4 unknown=0"}
    bad = dict(gold, markdown=gold["markdown"] + "\nSee also `src/caching.py`.\n")
    res = graders.paths_grounded(DECOY, bad, {})
    assert not res["passed"] and res["score"] == 0.8 and res["evidence"] == "paths=5 unknown=1: src/caching.py"
    assert not graders.paths_grounded(DECOY, dict(gold, markdown="# ADR 001: X\n"), {})["passed"]


def test_forbidden_path_absent_handles_na_full_and_bare_names():
    assert graders.forbidden_path_absent(CASES["adr-storage-session-001"], {}, {})["na"] is True
    gold = _gold(DECOY)
    assert graders.forbidden_path_absent(DECOY, gold, {})["passed"]
    for cite in ("`src/caching.py`", "`src\\caching.py`", "the module caching.py", "`src/db.py`"):
        assert not graders.forbidden_path_absent(DECOY, dict(gold, markdown=gold["markdown"] + cite), {})["passed"]
    # An extensionless forbidden path must not fire on its last segment used as a plain word.
    case = {"expected": {"forbidden_paths": ["src/services/orders"], "allowed_paths": ["src/api/routes/orders.ts"]}}
    assert graders.forbidden_path_absent(case, {"markdown": "The orders list changes."}, {})["passed"]
    assert not graders.forbidden_path_absent(case, {"markdown": "See `src/services/orders`."}, {})["passed"]


def test_constraints_named_supports_any_of_lists_and_na():
    assert graders.constraints_named(CASES["adr-tooling-ruff-009"], {}, {})["na"] is True
    gold = _gold(DECOY)
    assert graders.constraints_named(DECOY, gold, {})["passed"]
    swapped = dict(gold, markdown=gold["markdown"].replace("within 5 seconds", "within five seconds"))
    assert graders.constraints_named(DECOY, swapped, {})["passed"]  # any-of option
    missing = dict(gold, markdown="# ADR 001: X\n")
    assert graders.constraints_named(DECOY, missing, {}) == {"score": 0.0, "passed": False, "evidence": "not named: ['5 seconds']"}


def test_suite_metrics_parse_grader_evidence():
    rows = [
        {"grades": {"paths_grounded": {"evidence": "paths=4 unknown=0"},
                    "two_plus_alternatives": {"evidence": "alternatives=3 markdown_items=3"},
                    "sections_present": {"evidence": "all five headers present; words=650"}}},
        {"grades": {"paths_grounded": {"evidence": "paths=5 unknown=2: a, b"},
                    "two_plus_alternatives": {"evidence": "alternatives=2 markdown_items=2"},
                    "sections_present": {"evidence": "all five headers present; words=810"}}},
    ]
    assert graders.suite_metrics(rows) == {"unknown_paths_total": 2, "attempts_with_unknown_paths": "1/2",
                                           "mean_alternatives": 2.5, "mean_words": 730,
                                           "attempts_over_700_words": "1/2"}


# --------------------------------------------------------------------------- suite wiring


def test_cases_cover_the_required_strata_and_numbering():
    suite = load_suite(SKILL_DIR)
    assert len(suite.cases) == 10 and {c["source"] for c in suite.cases} == {"author-written"}
    strata: dict[str, int] = {}
    for c in suite.cases:
        strata[c["tags"][0]] = strata.get(c["tags"][0], 0) + 1
        exp = c["expected"]
        assert exp["allowed_paths"] == [f["path"] for f in c["input"]["context_pack"]]
        assert exp["number"] == adr.next_number(c["input"].get("existing_adrs") or [])
        assert 3 <= len(c["input"]["context_pack"]) <= 6
    assert strata == {"storage": 3, "messaging": 2, "api": 2, "tooling": 2, "tricky": 1}
    assert CASES["adr-storage-uploads-002"]["expected"]["number"] == 4
    for case in suite.cases:  # decoys are, by definition, outside the pack
        assert not set(case["expected"]["forbidden_paths"]) & set(case["expected"]["allowed_paths"])
        assert case.get("label_verified_by", "").startswith("claude-fable-5-1 ")  # CONTRACT.md section 3
    assert "src/caching.py" in DECOY["expected"]["forbidden_paths"]


def test_oracle_passes_every_applicable_metric_and_null_fails_every_case():
    suite = load_suite(SKILL_DIR)
    det = [m for m in suite.metrics if m["grader"] != "llm_rubric"]
    meta = {"skill": "adr", "status": "ok", "served_model": "oracle"}
    for case in suite.cases:
        ctx = GradeContext(case=case, output=case["expected"]["gold_output"], meta=meta, custom_module=suite.custom_module)
        for m in det:
            g = run_metric(m, ctx)
            assert g.passed or g.na, (case["id"], m["name"], g.evidence)
    assert smoke(suite)["null_baseline_passes"] == []


def test_harness_smoke_reports_ok():
    assert smoke(load_suite(SKILL_DIR))["ok"]
