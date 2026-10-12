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
Results are filled in from `evals/results/api/<skill>/latest/summary.json` after each
full run. See the per-skill sections below.
<!-- RESULTS:END -->

Every number above comes from the committed `latest/` report of that skill, produced by
`uv run evals/run.py`. Pass rates carry 95% Wilson intervals; cost is derived from the
tokens the API reported for the model that served the request; judge spend is kept
separate from skill spend. Rows that were truncated, refused, or failed for
infrastructure reasons are counted and shown, never averaged in as model failures.

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
