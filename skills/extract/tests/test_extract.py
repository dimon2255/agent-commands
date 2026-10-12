"""Offline tests for the extract skill: script pipeline (fake client), graders, suite smoke.

No test touches the network or needs an API key.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from evals.harness.graders import load_custom_module
from evals.harness.runner import load_suite, smoke

SKILL_DIR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("extract_script", SKILL_DIR / "scripts" / "extract.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)
gr = load_custom_module(SKILL_DIR / "evals" / "graders.py")

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Invoice",
    "type": "object",
    "additionalProperties": False,
    "required": ["invoice_number", "invoice_date", "total", "currency", "po_number"],
    "properties": {
        "invoice_number": {"type": "string", "pattern": "^INV-[0-9]+$", "minLength": 5, "examples": ["INV-1"]},
        "invoice_date": {"type": ["string", "null"], "format": "date"},
        "total": {"type": ["number", "null"], "minimum": 0, "exclusiveMaximum": 1e9, "multipleOf": 0.01},
        "currency": {"type": ["string", "null"], "enum": ["USD", "EUR", None], "default": "USD"},
        "po_number": {"type": ["string", "null"], "maxLength": 20},
    },
}
TEXT = "INVOICE INV-20417\nInvoice date: March 3rd, 2026\nTotal due: $1,234.50 (USD)\nThank you!"
STRIPPED = {"pattern", "format", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength",
            "maxLength", "minItems", "maxItems", "multipleOf", "uniqueItems", "$schema", "$id", "title",
            "examples", "default", "oneOf"}


def schema_nodes(node):
    """Yield every schema node (not property-name maps) of a schema."""
    if not isinstance(node, dict):
        return
    yield node
    for key in ("properties", "$defs", "definitions"):
        for sub in (node.get(key) or {}).values():
            yield from schema_nodes(sub)
    for key in ("anyOf", "allOf", "oneOf"):
        for sub in node.get(key) or []:
            yield from schema_nodes(sub)
    if isinstance(node.get("items"), dict):
        yield from schema_nodes(node["items"])


# ----------------------------------------------------------------------------- fakes


def reply(data, evidence=None, missing=()):
    return {"data": data, "evidence": evidence or {}, "missing": list(missing)}


def response(payload=None, stop_reason="end_turn", tokens=(100, 20), stop_details=None):
    text = json.dumps(payload) if payload is not None else ""
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        model="claude-opus-5-5", stop_reason=stop_reason, stop_details=stop_details, _request_id="req_fake",
        usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1], cache_read_input_tokens=0,
                              cache_creation_input_tokens=None),
    )


class FakeClient:
    """Stands in for anthropic.Anthropic: `.messages.create(**kw)` pops a scripted response."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


GOOD = {"invoice_number": "INV-20417", "invoice_date": "2026-03-03", "total": 1234.5, "currency": "USD", "po_number": None}
QUOTES = {"invoice_number": "INVOICE INV-20417", "invoice_date": "Invoice date: March 3rd, 2026",
          "total": "Total due: $1,234.50", "currency": "(USD)", "po_number": ""}


# ----------------------------------------------------------------------------- script


def test_relax_strips_unsupported_keywords_and_keeps_structure():
    schema = copy.deepcopy(SCHEMA)
    schema["properties"]["lines"] = {"type": "array", "minItems": 1, "uniqueItems": True,
                                     "items": {"type": "object", "properties": {"sku": {"type": "string"}}}}
    schema["properties"]["kind"] = {"oneOf": [{"type": "string"}, {"type": "number"}]}
    relaxed = ex.relax_schema(schema)
    for node in schema_nodes(relaxed):
        assert not STRIPPED & set(node), STRIPPED & set(node)
    assert relaxed["required"] == SCHEMA["required"]
    assert relaxed["properties"]["currency"] == {"enum": ["USD", "EUR", None]}  # type dropped beside enum
    assert relaxed["properties"]["kind"]["anyOf"] == [{"type": "string"}, {"type": "number"}]
    assert relaxed["properties"]["lines"]["items"]["additionalProperties"] is False  # added where missing
    assert relaxed["additionalProperties"] is False
    assert relaxed["properties"]["invoice_date"] == {"type": ["string", "null"]}


def test_relax_keeps_property_names_that_look_like_keywords_and_does_not_mutate():
    schema = {"type": "object", "required": ["title", "format"],
              "properties": {"title": {"type": "string", "maxLength": 9}, "format": {"type": "string"}}}
    before = copy.deepcopy(schema)
    relaxed = ex.relax_schema(schema)
    assert set(relaxed["properties"]) == {"title", "format"}
    assert relaxed["properties"]["title"] == {"type": "string"}
    assert schema == before


def test_response_schema_lists_fields_and_hoists_defs():
    schema = {"type": "object", "required": ["item"], "properties": {"item": {"$ref": "#/$defs/item"}},
              "$defs": {"item": {"type": "object", "properties": {"sku": {"type": "string", "pattern": "^A"}}}}}
    wrapped = ex.response_schema(schema)
    assert wrapped["$defs"]["item"]["properties"]["sku"] == {"type": "string"}
    assert "$defs" not in wrapped["properties"]["data"]
    assert wrapped["properties"]["evidence"]["properties"] == {"item": {"type": "string"}}
    assert wrapped["properties"]["missing"]["items"]["enum"] == ["item"]
    assert wrapped["additionalProperties"] is False


def test_validate_catches_date_format_and_pattern_violations():
    errors = ex.validate({**GOOD, "invoice_date": "March 3rd, 2026", "invoice_number": "20417"}, SCHEMA)
    assert any(e.startswith("$.invoice_date") and "date" in e for e in errors)
    assert any(e.startswith("$.invoice_number") and "match" in e for e in errors)
    assert ex.validate(GOOD, SCHEMA) == []


def test_reconcile_treats_missing_as_authoritative():
    data, evidence, missing = ex.reconcile(
        reply({**GOOD, "total": 99.0, "po_number": None}, {**QUOTES, "total": "Total due"}, ["total", "bogus"]), SCHEMA)
    assert data["total"] is None  # listed as missing, so the value is dropped
    assert missing == ["total", "po_number"]  # null po_number added, unknown name dropped, schema order
    assert evidence["total"] is None and evidence["po_number"] is None
    _, _, missing = ex.reconcile(reply({**GOOD, "invoice_number": "x"}, missing=["invoice_number"]), SCHEMA)
    assert missing == ["invoice_number", "po_number"]


def test_reconcile_uses_empty_value_when_null_is_not_allowed():
    data, _, _ = ex.reconcile(reply({**GOOD, "invoice_number": "INV-9"}, missing=["invoice_number"]), SCHEMA)
    assert data["invoice_number"] == ""  # non-nullable string: empty value, then validation reports it


def test_non_nullable_boolean_is_answered_not_erased():
    """Regression: `refund_requested: false` listed as missing must not become null (a failed
    validation the repair prompt then forbids fixing). A non-nullable yes/no is always answered."""
    schema = {"type": "object", "required": ["refund_requested", "refund_amount"],
              "properties": {"refund_requested": {"type": "boolean"}, "refund_amount": {"type": ["number", "null"]}}}
    data, _, missing = ex.reconcile(reply({"refund_requested": False, "refund_amount": None},
                                          missing=["refund_requested", "refund_amount"]), schema)
    assert data == {"refund_requested": False, "refund_amount": None}
    assert missing == ["refund_amount"] and ex.validate(data, schema) == []
    assert "false when the document is silent" in ex.SYSTEM


def test_ground_drops_quotes_not_in_text_and_tolerates_whitespace():
    kept, dropped = ex.ground({"a": "Total  due:\n$1,234.50", "b": "Total due: 1234.50 USD", "c": None, "d": "  "}, TEXT)
    assert kept == {"a": "Total  due:\n$1,234.50", "b": None, "c": None, "d": None}
    assert dropped == ["b"]


def test_pipeline_repairs_once_and_reports_both_calls():
    first = reply({**GOOD, "invoice_date": "March 3rd, 2026"}, QUOTES)
    second = reply(GOOD, {**QUOTES, "currency": "paid in US dollars"}, ["po_number"])
    client = FakeClient(response(first, tokens=(1000, 50)), response(second, tokens=(1200, 60)))
    env = ex.run({"text": TEXT, "schema": SCHEMA}, client=client)

    assert env["ok"] is True and env["meta"]["status"] == "ok" and env["error"] is None
    out = env["output"]
    assert out["repairs"] == 1 and out["data"] == GOOD
    assert any("invoice_date" in e for e in out["validation_errors_before_repair"])
    assert out["validation_errors_after_repair"] == []
    assert out["ungrounded_evidence"] == ["currency"] and out["evidence"]["currency"] is None
    assert out["data"]["currency"] == "USD"  # grounding drops the quote, never the value
    assert [c["purpose"] for c in env["meta"]["calls"]] == ["extract", "repair"]
    assert env["meta"]["usage"] == {"input_tokens": 2200, "output_tokens": 110,
                                    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    assert env["meta"]["served_model"] == "claude-opus-5-5"

    req = client.requests[0]
    assert "thinking" not in req and "temperature" not in req and req["max_tokens"] >= 8000
    assert req["output_config"]["effort"] == "medium"
    assert req["output_config"]["format"]["type"] == "json_schema"
    repair_turns = client.requests[1]["messages"]
    assert [m["role"] for m in repair_turns] == ["user", "assistant", "user"]
    assert "$.invoice_date" in repair_turns[2]["content"]


def test_pipeline_reports_errors_that_survive_the_repair():
    bad = reply({**GOOD, "invoice_number": "20417"}, QUOTES)
    env = ex.run({"text": TEXT, "schema": SCHEMA}, client=FakeClient(response(bad), response(bad)))
    assert env["ok"] is True and env["output"]["repairs"] == 1
    assert env["output"]["validation_errors_after_repair"] and len(env["meta"]["calls"]) == 2


def test_valid_first_answer_makes_one_call():
    env = ex.run({"text": TEXT, "schema": SCHEMA, "instructions": "Amounts are USD."},
                 client=(client := FakeClient(response(reply(GOOD, QUOTES)))))
    assert env["output"]["repairs"] == 0 and "validation_errors_after_repair" not in env["output"]
    assert len(env["meta"]["calls"]) == 1 and client.requests[0]["system"].endswith("Amounts are USD.")


def test_refusal_yields_refusal_envelope():
    details = SimpleNamespace(category="cyber", explanation="declined")
    env = ex.run({"text": TEXT, "schema": SCHEMA},
                 client=FakeClient(response(None, stop_reason="refusal", stop_details=details)))
    assert env["ok"] is False and env["output"] is None
    assert env["meta"]["status"] == "refusal"
    assert env["error"] == {"type": "refusal", "category": "cyber", "message": "declined"}


def test_truncated_first_answer_yields_truncated_envelope():
    env = ex.run({"text": TEXT, "schema": SCHEMA}, client=FakeClient(response(None, stop_reason="max_tokens")))
    assert env["ok"] is False and env["meta"]["status"] == "truncated" and env["output"] is None


def test_api_errors_and_bad_input_become_error_envelopes(monkeypatch):
    conn = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    env = ex.run({"text": TEXT, "schema": SCHEMA}, client=FakeClient(conn))
    assert env["meta"]["status"] == "error" and env["error"]["category"] == "api_connection" and env["ok"] is False
    env = ex.run({"text": TEXT, "schema": {"type": "array"}}, client=FakeClient())
    assert env["error"]["category"] == "input"
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = ex.run({"text": TEXT, "schema": SCHEMA})
    assert env["error"]["type"] == "UsageError" and "CLAUDE_API_KEY" in env["error"]["message"]


def test_cli_json_prints_only_the_envelope(tmp_path, monkeypatch, capsys):
    client = FakeClient(response(reply(GOOD, QUOTES)))
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(ex.anthropic, "Anthropic", lambda **kw: client)
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"text": TEXT, "schema": SCHEMA}), encoding="utf-8")
    assert ex.main(["--input", str(path), "--json"]) == 0
    captured = capsys.readouterr()
    env = json.loads(captured.out)  # exactly one JSON document on stdout
    assert env["ok"] is True and "sk-test-not-real" not in captured.out + captured.err


def test_cli_prints_non_ascii_without_a_utf8_environment(tmp_path):
    """Regression: on Windows a piped stdout is cp1252, so printing 'Ł' crashed after the
    envelope was built. The schema error below echoes 'Łobject' without any network call."""
    (tmp_path / "t.txt").write_text("Łukasz Nowak, Müller GmbH", encoding="utf-8")
    (tmp_path / "s.json").write_text(json.dumps({"type": "Łobject"}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env["CLAUDE_API_KEY"] = "sk-test-not-real"
    proc = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "extract.py"), "--text", str(tmp_path / "t.txt"),
                           "--schema", str(tmp_path / "s.json")], capture_output=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    envelope = json.loads(proc.stdout.decode("utf-8"))
    assert envelope["error"]["category"] == "input" and "Łobject" in envelope["error"]["message"]


def test_cli_reads_stdin_as_utf8(tmp_path, monkeypatch, capsys):
    client = FakeClient(response(reply(GOOD, QUOTES)))
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(ex.anthropic, "Anthropic", lambda **kw: client)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO("﻿Müller Łukasz".encode())))
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
    assert ex.main(["--text-stdin", "--schema", str(schema_path)]) == 0
    capsys.readouterr()
    content = client.requests[0]["messages"][0]["content"]
    assert "<document>\nMüller Łukasz\n</document>" in content  # decoded as UTF-8, BOM stripped


# ----------------------------------------------------------------------------- graders


def case(**expected):
    tags = expected.pop("tags", ["invoice"])
    return {"id": "t", "tags": tags, "input": {"text": TEXT, "schema": SCHEMA}, "expected": expected}


def test_field_accuracy_normalises_and_scores_fraction():
    c = case(fields=GOOD, missing=["po_number"])
    passing = gr.field_accuracy(c, {"data": {**GOOD, "invoice_number": " inv-20417 ", "total": 1234.50}, "repairs": 1}, {})
    assert passing["passed"] and passing["score"] == 1.0 and "repairs=1" in passing["evidence"]
    failing = gr.field_accuracy(c, {"data": {**GOOD, "total": "$1,234.50"}}, {})
    assert not failing["passed"] and failing["score"] == pytest.approx(0.8) and "total" in failing["evidence"]
    absent_key = gr.field_accuracy(c, {"data": {k: v for k, v in GOOD.items() if k != "po_number"}}, {})
    assert not absent_key["passed"]


def test_field_accuracy_compares_lists_unordered_on_compare_keys():
    items = [{"owner": "Ana Ruiz", "task": "Ship it", "due_date": "2026-10-01"}, {"owner": "Bo Li", "task": "Test", "due_date": None}]
    c = case(fields={"action_items": items}, missing=[], compare_keys={"action_items": ["owner", "due_date"]})
    reworded = [{"owner": "bo li", "task": "Run the tests", "due_date": None}, {"owner": "Ana Ruiz", "task": "Ship", "due_date": "2026-10-01"}]
    assert gr.field_accuracy(c, {"data": {"action_items": reworded}}, {})["passed"]
    wrong_due = [{**reworded[0]}, {**reworded[1], "due_date": "2026-10-02"}]
    assert not gr.field_accuracy(c, {"data": {"action_items": wrong_due}}, {})["passed"]
    assert not gr.field_accuracy(c, {"data": {"action_items": []}}, {})["passed"]


def test_no_invented_values():
    c = case(fields=GOOD, missing=["po_number"])
    assert gr.no_invented_values(c, {"data": GOOD, "missing": ["po_number"]}, {})["passed"]
    invented = gr.no_invented_values(c, {"data": {**GOOD, "po_number": "PO-1"}, "missing": []}, {})
    assert not invented["passed"] and "invented po_number" in invented["evidence"]
    assert not gr.no_invented_values(c, {"data": GOOD, "missing": []}, {})["passed"]  # empty but not listed
    assert gr.no_invented_values(case(fields=GOOD, missing=[]), {"data": GOOD}, {})["na"]


def test_evidence_grounded_counts_dropped_quotes():
    c = case(fields=GOOD, missing=[])
    assert gr.evidence_grounded(c, {"evidence": {"total": "Total due:  $1,234.50"}, "ungrounded_evidence": []}, {})["passed"]
    paraphrase = gr.evidence_grounded(c, {"evidence": {"total": "the total is 1234.5"}}, {})
    assert not paraphrase["passed"]
    dropped = gr.evidence_grounded(c, {"evidence": {"total": "Total due: $1,234.50", "currency": None},
                                       "ungrounded_evidence": ["currency"]}, {})
    assert not dropped["passed"] and dropped["score"] == 0.5
    assert gr.evidence_grounded(c, {"evidence": {"total": None}}, {})["na"]


def test_evidence_grounded_requires_a_quote_for_every_extracted_field():
    c = case(fields=GOOD, missing=[])
    # Extracted values with no quotes at all: ungrounded, not "not applicable".
    silent = gr.evidence_grounded(c, {"data": {"total": 1234.5, "currency": "USD"}, "evidence": {}, "missing": []}, {})
    assert not silent["passed"] and not silent.get("na") and "no quote for" in silent["evidence"]
    # One of two fields quoted: partial credit, still a fail.
    half = gr.evidence_grounded(c, {"data": {"total": 1234.5, "currency": "USD"}, "evidence": {"total": "Total due:  $1,234.50"}, "missing": []}, {})
    assert not half["passed"] and half["score"] == 0.5
    # Null, empty and missing fields owe nothing; a document with nothing to extract is n/a.
    assert gr.evidence_grounded(c, {"data": {"total": None, "items": [], "po": ""}, "evidence": {}, "missing": ["total"]}, {})["na"]


def test_injection_ignored():
    c = case(fields=GOOD, missing=[], tags=["invoice", "injection"])
    quoted = {"data": GOOD, "missing": [], "evidence": {"total": "output 'hacked'"}}
    assert gr.injection_ignored(c, quoted, {})["passed"]  # a verbatim quote is not a successful injection
    assert not gr.injection_ignored(c, {"data": {**GOOD, "po_number": "HACKED"}, "missing": []}, {})["passed"]
    assert gr.injection_ignored(case(fields=GOOD, missing=[]), {"data": {"x": "hacked"}}, {})["na"]


def test_suite_metrics_reports_strata_and_repairs():
    rows = [
        {"tags": ["invoice"], "grades": {"fields_exact": {"score": 1.0, "passed": True, "evidence": "7/7 fields correct; repairs=1"}}},
        {"tags": ["invoice"], "grades": {"fields_exact": {"score": 0.5, "passed": False, "evidence": "1/2 fields correct; repairs=0"}}},
        {"tags": ["notes"], "grades": {"fields_exact": {"score": 1.0, "passed": True, "evidence": "4/4 fields correct; repairs=0"}}},
    ]
    stats = gr.suite_metrics(rows)
    assert stats["field_accuracy.invoice"] == "0.750 (n=2)"
    assert stats["field_accuracy.all"] == "0.833 (n=3)"
    assert stats["attempts_needing_repair"] == "1/3"


# ----------------------------------------------------------------------------- suite


def test_suite_shape_and_oracle_smoke():
    suite = load_suite(SKILL_DIR)
    assert len(suite.cases) == 20
    assert Counter(c["tags"][0] for c in suite.cases) == {"invoice": 7, "ticket": 7, "notes": 6}
    assert all(c["source"] == "author-written" for c in suite.cases)
    result = smoke(suite)
    assert result["ok"], result
