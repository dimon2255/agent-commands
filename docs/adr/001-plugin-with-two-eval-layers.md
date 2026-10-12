# ADR 001: One Claude Code plugin, two evaluation layers

**Status:** Accepted, 2026-10-12

## Context

The repository exists to demonstrate production-grade AI engineering: skills that do real
work, and evidence that they do it. A skill in Claude Code is a `SKILL.md` that Claude
follows inside the agent, so the obvious way to test it is to run the agent. But agent
runs are slow, cost subscription quota, cannot run shell on native Windows, and give
coarse pass/fail signals through a small set of graders. Fine-grained questions
(field-level accuracy, judge agreement with human labels, hallucinated file paths) need
dozens of cases, repeated runs, confidence intervals and cost accounting.

## Decision

Package the three skills as one plugin (`.claude-plugin/plugin.json`, installable from the
repo's own marketplace) and test each skill at two layers:

1. **API-level suite** (`evals/harness`, `uv run evals/run.py`): each skill bundles a
   standalone script that does the work through the Anthropic SDK and emits a fixed
   envelope. The harness runs that script per case, classifies every attempt (scored,
   truncated, refusal, infrastructure error), applies atomic graders, and reports pass
   rates with Wilson intervals, token-derived cost and latency. Reference answers are
   human-written; an oracle and a null baseline run through the graders without API calls.
2. **Native suite** (`evals/native`, `claude plugin eval .`): two or three cases per skill
   check that the skill triggers and completes a small task inside the agent, with an
   ablation arm (plugin absent) so the plugin's contribution is measured, not assumed.

## Consequences

- Positive: the measured artifact is the shipped entry point; results are reproducible
  (`uv.lock`, pinned model IDs, committed `latest/` summaries); the two layers answer
  different questions and neither pretends to answer the other's.
- Negative: each skill carries a script and an inline path in `SKILL.md`, which must stay
  consistent. The judge model defaults to the same family as the model under test; the
  README names this as a known self-preference risk and the flag that changes it.
- The eval-audit checklist in Anthropic's `claude-api` skill was used as the construction
  checklist for the harness; items it demands (errors sidecar, truncation status, served
  model assertion, separate judge cost, reps with intervals) are implemented, not noted.
