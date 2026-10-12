# agent-commands

[![ci](https://github.com/dimon2255/agent-commands/actions/workflows/ci.yml/badge.svg)](https://github.com/dimon2255/agent-commands/actions/workflows/ci.yml)
[![api-evals](https://github.com/dimon2255/agent-commands/actions/workflows/evals.yml/badge.svg)](https://github.com/dimon2255/agent-commands/actions/workflows/evals.yml)

Three production-shaped [Claude Code](https://code.claude.com) skills, each shipped with a
measured evaluation suite. The point of the repository is not the skills alone but the
evidence: every skill has a labelled case set, atomic graders, confidence intervals,
token-derived cost, and a free oracle/null smoke test that runs in CI.

| Skill | What it does | The engineering it demonstrates |
|---|---|---|
| **`/extract`** | Pulls fields out of unstructured text into JSON that validates against a schema you supply, with a verbatim evidence quote per field and an explicit list of fields the text does not state. | Structured outputs, schema relaxation for the output grammar vs. strict validation afterwards, a bounded validate-and-repair loop, deterministic grounding checks, prompt-injection resistance. |
| **`/judge`** | Grades a model output against a rubric (pointwise), compares two outputs (pairwise), or calibrates the judge against human labels. | LLM-as-judge with the controls an eval engineer is expected to know: order swap for position bias, verbosity guard, untrusted-candidate framing, Python-side pass rule, Cohen's kappa against human labels, known-negative probes. |
| **`/adr`** | Writes an Architecture Decision Record grounded in the files Claude actually read, with at least two alternatives and concrete negative consequences, and flags any file path the model invented. | Agentic context gathering separated from a deterministic drafting step so it can be evaluated; hallucination detection by construction; house-style enforcement by graders rather than by hope. |

## Results

<!-- RESULTS:START -->
API-level suites, model under test `claude-opus-5-5`, run 2026-10-12. Pass rate is over
scored attempts; the bracket is the 95% Wilson interval.

| Skill | Cases × reps | Headline metrics | Cost per attempt | Haiku 5.5 on the same suite |
|---|---|---|---|---|
| `extract` | 20 × 2 | `schema_valid` 40/40 [91%, 100%] · `fields_exact` 40/40 · `no_invented_values` 24/24 · `evidence_grounded` 38/38 · `injection_ignored` 6/6 · 0 repairs needed | $0.016 | 20/20 on every metric at $0.0006 per attempt |
| `judge` | 34 × 2 | `agrees_with_human` 48/48 [93%, 100%] · Cohen's κ 1.00, weighted κ 0.98 · `picks_correct_winner` 20/20 · `position_consistent` 20/20 (flip rate 0) · `known_negative_fails` 8/8 | $0.020 | 34/34, κ 1.00, weighted κ 0.96 at $0.0006 |
| `adr` | pending | pending | pending | pending |

Native `claude plugin eval` (inside Claude Code, two-arm ablation, 2 runs per case):
pending final run.

What these numbers do and do not say: both finished suites are **saturated**. The model
under test passes every case, and so does the cheapest current model, so the suites
cannot rank models; they work as regression guards for the skills' logic (grounding,
repair, order swap, pass rule) and as cost baselines. The hardening backlog in
`docs/PROGRESS.md` lists the harder cases needed to open a gap (OCR-noisy and
multi-page documents, nested schemas, conflicting values, borderline judgements labelled
by a second person).
<!-- RESULTS:END -->

Every number above comes from the committed `latest/` report of that skill, produced by
`uv run evals/run.py`. Pass rates carry 95% Wilson intervals; cost is derived from the
tokens the API reported for the model that served the request; judge spend is kept
separate from skill spend. Rows that were truncated, refused, or failed for
infrastructure reasons are counted and shown, never averaged in as model failures.

## The skills in detail

### `extract`: schema-guided extraction with evidence

Asking a model to "pull the fields out" fails in predictable ways: it computes a due
date from "Net 30", sums line items into a total nobody printed, picks the ship date
instead of the invoice date, returns `"$1,234.50"` where a number was wanted, and
"corrects" an email address that only looked like a typo. Each step of the skill removes
one of those failures.

- The user's JSON Schema is **relaxed** for the API's structured-output grammar (which
  rejects `pattern`, `format`, `minimum`, schema-valued `additionalProperties` and more,
  see [ADR 003](docs/adr/003-schema-relaxation-for-structured-outputs.md)) and the result
  is then **validated against the full schema** with format checks. One repair pass shows
  the model the violations; anything still invalid is returned with the errors listed,
  never hidden.
- A field the text does not state is `null` and listed in `missing`. A guess is worse than
  a gap because nothing downstream can tell them apart.
- Every top-level field carries the shortest **verbatim quote** that supports it. Quotes
  that cannot be found in the text are dropped in Python and reported, so evidence is
  checked by code rather than by the model's say-so.
- Text is untrusted data: instructions planted inside the document are content.

The 20-case suite spans invoices, support tickets and meeting notes and includes two-date
and subtotal-versus-total distractors, three currency notations, an enum near-miss, a
typo-looking email that must be copied not corrected, three prompt-injection documents,
two meetings with zero action items, and one document unrelated to the schema (every
field must be null). Metrics: `schema_valid`, `fields_exact`, `no_invented_values`,
`evidence_grounded`, `injection_ignored`.

### `judge`: LLM-as-judge with the controls that make it trustworthy

An LLM judge left alone prefers the longer answer, the answer shown first, the answer
labelled "reference", and text that sounds like its own; it follows instructions planted
in what it grades; and it gives holistic verdicts nobody can audit.

- **Pointwise**: named criteria, a verbatim quote per criterion, and the pass rule
  (`all` or `majority`) applied in Python to the per-criterion verdicts. The model's own
  overall verdict is kept as `model_passed` for comparison but never trusted.
- **Pairwise**: two independent calls, A-then-B and B-then-A, with positional labels only.
  A verdict that flips with order is reported as a `tie` with `position_consistent: false`
  instead of being averaged away. Length is explicitly not quality.
- **Calibrate**: before trusting the judge on a new rubric, run it over human-labelled
  items and read agreement, Cohen's kappa, quadratic-weighted kappa and the
  majority-class baseline.
- The candidate is fenced as untrusted data; a reference answer is renamed "additional
  context, which may itself be imperfect" so the judge cannot defer to a label.

The 34-case suite uses four rubrics (support reply, SQL, two-sentence summary, code review
comment): 20 pointwise items with human pass/fail and 1–5 labels (6 borderline), 10
pairwise items including 3 where the shorter answer is correct and 2 near-identical pairs
with one factual slip, and 4 known negatives (empty, "I don't know", a confident answer to
a different question, an injected "mark this as passed"). Suite-level statistics: kappa
against the labels, agreement split by clear-cut versus borderline, and position-flip rate.

### `adr`: architecture decision records grounded in the code

An ADR written from memory cites files that do not exist, lists alternatives for show,
and records only benefits. The skill separates the agentic part (Claude Code gathers the
relevant files, existing ADRs and constraints into a context pack) from a deterministic
drafting step that can be evaluated.

- One structured-output call drafts the record in the house format: status, context that
  cites files from the pack, decision, at least two alternatives each with a reason for
  rejection, positive and negative consequences.
- Python computes the next ADR number, scans the markdown for every path-like token and
  classifies each as present in the pack or **unknown**. Unknown paths are reported, not
  silently deleted, so a hallucinated reference fails the eval instead of shipping.
- Deterministic post-checks flag fewer than two alternatives, no negative consequence,
  missing sections and placeholder words.

The 10-case suite uses small synthetic codebases (3–6 files each) where the right decision
depends on the pack: a README constraint that forbids the obvious choice, a decoy path
(`src/caching.py` mentioned in a comment while only `src/cache.py` exists), existing ADRs
that fix the next number, and a thin pack where assumptions must be stated. Metrics:
`sections_present`, `two_plus_alternatives`, `negative_consequence_present`,
`paths_grounded`, `forbidden_path_absent`, `number_correct`, `no_placeholders`,
`constraints_named`, and an LLM-rubric `decision_fits_context`.

## Install

```bash
claude plugin marketplace add dimon2255/agent-commands
claude plugin install agent-commands@dimon2255
```

Then, inside Claude Code:

```
/agent-commands:extract invoice.txt --schema schemas/invoice.json
/agent-commands:judge pairwise --rubric rubric.yaml --task "..." --candidate-a a.md --candidate-b b.md
/agent-commands:adr "Where should session state live now that we run three API replicas?"
```

Each skill also works as a plain script with no Claude Code at all
(`uv run skills/<skill>/scripts/<skill>.py --help`); that script is exactly what the
evals measure.

## How the evals work

Two layers, two questions. The **API-level suite** (`evals/harness`, `uv run evals/run.py`)
runs each skill's script as a subprocess per case, classifies every attempt (scored,
truncated, refusal, infrastructure error), applies one-property-per-metric graders and
writes a report with intervals, cost and latency. The **native suite** (`evals/native`,
`claude plugin eval .`) checks that each skill triggers on a plain-language request inside
the agent and completes a small task, with an ablation arm that measures what the plugin
adds over no plugin.

The harness was built against Anthropic's eval-audit checklist; the rules it enforces in
code (errors sidecar, truncation status, served-model assertion, separate judge cost,
gold-through-graders oracle, null baseline, both-direction cases, reps with intervals) are
listed in [`evals/README.md`](evals/README.md). The contract every skill script follows is
in [`evals/CONTRACT.md`](evals/CONTRACT.md).

Honesty notes, because an eval is only as good as what it admits:

- Case sets and labels were written by the repository author while building the suites,
  with AI assistance from a different model than the one under test (`source:
  author-written` on every case). They are not an external benchmark.
- The default judge model is the same family as the model under test. That is a known
  self-preference risk; `--judge-model` changes it and the reports record which judge ran.
- With 10–34 cases per suite and one repetition, the intervals are wide (roughly ±15–25
  points). The suites detect gross regressions and grader bugs; they do not resolve
  single-digit differences. `--reps` narrows them at proportional cost.
- Native Windows cannot sandbox shell tools for `claude plugin eval`, so the native cases
  grant only read-only tools plus `Skill` and `Write`, and each `SKILL.md` documents an
  inline path that needs no script.

## Repository layout

```
.claude-plugin/        plugin.json + marketplace.json (install as agent-commands@dimon2255)
skills/<skill>/        SKILL.md, scripts/<skill>.py, references/, evals/ (cases, config, graders), tests/
evals/harness/         shared runner, graders, stats, pricing, report
evals/native/          claude plugin eval cases (case.yaml + graders/*.md)
evals/results/api/     committed latest/ report per skill
docs/                  PROGRESS.md, adr/ (decisions behind this repo), diagrams/
tests/                 harness tests on a fake skill fixture (no network)
```

## Development

```bash
uv sync
uv run pytest -q                       # harness + skill unit tests, no network
uv run ruff check .
uv run evals/run.py --all --smoke      # oracle + null baseline through the graders, free
set CLAUDE_API_KEY=sk-ant-...          # export on POSIX
uv run evals/run.py --skill extract --reps 2 --concurrency 4
claude plugin validate . --strict
claude plugin eval . --trust-plugin --no-publish --allow-tools Write
```

Design decisions are recorded where they belong: [`docs/adr/`](docs/adr/).

## License

MIT
