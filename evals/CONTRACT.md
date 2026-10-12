# Skill script and eval contract

Every skill in this repository has two faces:

1. **`SKILL.md`** — instructions Claude Code follows when the skill is invoked
   (`/agent-commands:<skill> ...`). It explains the method and, where a deterministic
   batch path exists, tells Claude to run the bundled script.
2. **`scripts/<skill>.py`** — a standalone, PEP 723 script (`uv run scripts/<skill>.py`)
   that performs the work through the Anthropic SDK and emits a machine-readable
   envelope. The API-level eval harness calls this script as the *real entry point*,
   so what is measured is what ships.

This file is the contract between the three skills and `evals/harness/`. Builders code
against it; the harness enforces it.

## 1. Script CLI

```
python skills/<skill>/scripts/<skill>.py --input <case_input.json> --json
        [--model claude-opus-5-5] [--effort low|medium|high|xhigh|max]
        [--out <file>]
```

- `--input` is a JSON file holding exactly the `input` object of an eval case (see §3).
  Scripts may also accept friendlier flags for humans (`--text`, `--schema`, ...);
  `--input/--json` is the mandatory machine path.
- With `--json`, **stdout carries only the envelope JSON** (one document). Logs go to stderr.
- Exit code 0 whenever an envelope was produced, even if `ok=false`. A non-zero exit
  means the script itself crashed; the harness files that as an infrastructure error, not
  a model failure.
- Credentials: read `CLAUDE_API_KEY`, falling back to `ANTHROPIC_API_KEY`, and pass the key
  explicitly to `anthropic.Anthropic(api_key=...)`. Never print the key.
- Default model `claude-opus-5-5`. Thinking is always on for this model: do not send a
  `thinking` parameter or `temperature`; control depth with `output_config={"effort": ...}`.
- Prefer `output_config={"format": {"type": "json_schema", "schema": ...}}` for structured
  results. Keep `max_tokens` generous (≥ 8000) so answers are not clipped.
- Dependencies are declared inline so the script runs anywhere:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic>=1.13,<2", "jsonschema>=4.23"]
# ///
```

## 2. Envelope (stdout with `--json`)

```json
{
  "ok": true,
  "output": { "...skill-specific result..." },
  "error": null,
  "meta": {
    "skill": "extract",
    "version": "0.1.0",
    "requested_model": "claude-opus-5-5",
    "served_model": "claude-opus-5-5",
    "status": "ok",
    "stop_reason": "end_turn",
    "usage": {
      "input_tokens": 1234, "output_tokens": 321,
      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0
    },
    "latency_ms": 2890,
    "calls": [
      {
        "purpose": "extract",
        "model": "claude-opus-5-5",
        "stop_reason": "end_turn",
        "usage": { "input_tokens": 1234, "output_tokens": 321,
                   "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0 },
        "latency_ms": 2890,
        "request_id": "req_..."
      }
    ]
  }
}
```

Rules the harness relies on:

| Field | Rule |
|---|---|
| `meta.status` | `ok`, `truncated` (any call hit `max_tokens`), `refusal` (any call returned `stop_reason: refusal`), or `error` (API error after SDK retries, or the script could not produce an output). |
| `ok` | `true` only when `status == "ok"` and `output` is present. |
| `error` | `null`, or `{"type": "<exception class or category>", "message": "..."}`. |
| `meta.served_model` | `response.model` of the *first* call. The harness fails the attempt loudly if it differs from `requested_model`. |
| `meta.usage` | Sum of all calls' usage, read from `response.usage`, never estimated. |
| `meta.latency_ms` | Sum of the model-call latencies (time around the SDK call only; no file I/O, no post-processing). |
| `meta.calls` | One entry per model call, in order, with its own `purpose` (`extract`, `repair`, `judge`, `draft`, ...). |

On a refusal, set `status: "refusal"`, `ok: false`, `output: null`, and put
`stop_details` (category, explanation) into `error`.

## 3. Eval cases — `skills/<skill>/evals/cases.jsonl`

One JSON object per line:

```json
{"id": "extract-invoice-001", "tags": ["invoice", "clean"], "source": "human-written",
 "input": { ... }, "expected": { ... }, "notes": "optional free text"}
```

- `id` unique within the skill; `tags[0]` is the stratum used for balance reporting.
- `source` is one of `human-written`, `author-written` (written and labelled by the repo
  author with AI assistance while building the suite), `human-verified`, or
  `synthetic-model:<model-id>`. Reference answers must never come from the model under
  test. When labels were drafted with the same model family as the one under test, add
  `label_verified_by: "<model-id or person> (<what was checked>, <date>)"` naming the
  independent reviewer; the README must say so.
- `input` is passed verbatim to the script. `expected` is only visible to graders.
- Put a **gold output** under `expected.gold_output` so the harness can run the oracle
  smoke test (gold through the graders must pass), and define `null_output` in the
  config so the null baseline (must fail) can run. Both run without API calls.
- Cover both directions: at least some cases where the right answer is "absent", "none",
  "cannot determine", or a refusal to invent.

## 4. Eval config — `skills/<skill>/evals/config.yaml`

```yaml
skill: extract
entrypoint: scripts/extract.py        # relative to the skill directory
cases: evals/cases.jsonl
graders_module: evals/graders.py      # optional, custom python graders
timeout_seconds: 240                  # hard wall-clock ceiling per attempt
null_output: {}                       # what an empty/no-op answer looks like
metrics:
  - name: schema_valid
    grader: json_schema
    schema: "$input.schema"
    target: "$output.data"
  - name: fields_exact
    grader: python
    function: field_accuracy          # in graders_module
  - name: no_invented_values
    grader: python
    function: no_hallucinated_fields
  - name: readable_rationale
    grader: llm_rubric
    rubric: "$expected.rubric"        # or an inline string
    target: "$output.rationale"
thresholds:                            # suite gates; CI fails when a metric is below
  schema_valid: 0.95
  fields_exact: 0.85
```

`$input.x`, `$output.x`, `$expected.x` and `$meta.x` are dotted-path references resolved
per case. Anything else is a literal.

### Built-in graders

| grader | args | passes when |
|---|---|---|
| `exact` | `target`, `expected` | normalised strings equal (trim, casefold, whitespace, `4` == `4.0`) |
| `contains` | `target`, `needle` | needle appears in target (normalised) |
| `regex` | `target`, `pattern`, `flags` | pattern found |
| `json_schema` | `target`, `schema` | target validates against the JSON Schema |
| `paths_subset` | `target` (list of paths), `allowed` (list) | every path in target is in allowed |
| `llm_rubric` | `target`, `rubric`, optional `context` | judge model votes PASS (structured output, 1..5 score) |
| `python` | `function` | `function(case, output, meta) -> {"score", "passed", "evidence"}` |

Every grader returns `{"score": 0..1, "passed": bool, "evidence": "short, human-readable"}`.
A python grader may instead return `{"na": true, "evidence": "..."}` when the metric does
not apply to that case (for example a pairwise metric on a pointwise case); such grades are
excluded from `n`. Keep metrics **atomic** (one property each) so a failure is diagnosable.

A `graders_module` may also define `suite_metrics(rows) -> dict` (rows are the scored
`results.jsonl` rows, each with `case_id`, `tags`, `grades`, and the envelope is in
`trajectories/`); the dict is placed in `summary.json` under `suite_metrics` and rendered
in the report. Use it for statistics that only exist across cases (Cohen's kappa,
position-flip rate, majority-class baseline). Rows carry `grades[<metric>]["evidence"]`,
so put whatever the suite statistic needs into a grader's evidence string or compute it
from `case["expected"]` by re-reading `cases.jsonl`.

## 5. What the harness writes

```
evals/results/api/<skill>/<timestamp>/
  results.jsonl       one row per (case, rep) that produced a scorable output
  errors.jsonl        attempts that did not: timeout, crash, api_error, served_model_mismatch
  trajectories/       full input + envelope + grades per attempt
  summary.json        pass rate per metric with Wilson 95% CI, cost, latency, gates
  report.md           the human-readable version
evals/results/api/<skill>/latest/   copy of summary.json, report.md, results.jsonl, errors.jsonl
```

Rows with `status: truncated` are shown but not averaged in as failures. Refusals are
reported as their own rate. Judge usage and cost are recorded separately from the
skill's own usage. Cost is derived from recorded tokens and the served model's price.

## 6. Native Claude Code evals — `evals/native/<skill>-<case>/`

Each skill also ships 2–3 `claude plugin eval` cases (`case.yaml` + `graders/*.md`) that
check the skill triggers and completes a small task inside the agent. They may only grant
read-only tools plus `Skill` (and `Write` where a file is produced); native Windows cannot
sandbox `Bash`, so `SKILL.md` must describe an inline path that works without running the
script.
