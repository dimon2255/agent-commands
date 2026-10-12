# Evaluation methodology

Two layers, two questions.

| Layer | Question it answers | How to run | Cost |
|---|---|---|---|
| **API-level** (`evals/harness`) | Does the skill's logic produce correct, grounded, well-formed output across a labelled case set, and at what cost and latency? | `uv run evals/run.py --all` | Anthropic API spend on `CLAUDE_API_KEY` |
| **Native** (`evals/native`) | Inside Claude Code, does the skill trigger on a plain-language request and finish the task, and how much does the plugin add over no plugin? | `claude plugin eval . --trust-plugin --no-publish --allow-tools Write` | Claude Code subscription quota |

## Design rules the harness enforces

The harness was built against Anthropic's eval-audit checklist (the one shipped in the
`claude-api` skill). The items below are implemented in code, not aspirations.

**The measured artifact is the shipped one.** Each skill's `scripts/<skill>.py` is run as
a subprocess with the same flags a user would type. There is no re-implementation of the
skill inside the harness (`evals/harness/runner.py`, `_run_script`).

**Infrastructure failures never become model failures.** Timeouts, crashes, unparseable
stdout, contract violations, API errors after retries and served-model mismatches go to
`errors.jsonl` with a failure class. They are counted and shown, never averaged into a
pass rate (`runner.py`, `report.py`).

**Clipped and refused answers are their own outcomes.** `status: truncated` rows are
graded but excluded from pass rates; refusals are reported as a rate. A skill that
cannot answer is not the same as a skill that answers wrongly.

**The served model is asserted.** `response.model` is recorded per call; an attempt served
by a different model than requested is an error row, because a number from the wrong
model measures nothing.

**Cost comes from recorded tokens.** Usage is read from `response.usage` per call and
priced by the served model (`pricing.py`). Judge usage and cost are recorded on their own
fields so the judge never hides inside the skill's cost.

**Latency is the model call only.** Subprocess start-up, grading and retries are excluded
from `latency_ms`; wall time is kept separately.

**Graders are atomic.** Each metric checks one property and returns
`{score, passed, evidence}`. A failure names the property and the evidence, so a surprising
score can be traced without re-running (`graders.py`; full trajectories are saved per
attempt).

**Every case ships a gold answer and the suite ships a null answer.** `--smoke` runs the
gold output through the deterministic graders (must pass) and the configured null output
(must fail) with no API calls. This runs in CI and catches wiring bugs before money is
spent.

**Reference answers are labelled, then independently re-checked.** Cases were drafted by
builder agents on `claude-opus-5-5`, the model under test, so every label was re-derived by
a different model (`claude-fable-5-1`) and the check is recorded per case as
`label_verified_by`. The contract requires that note whenever labels share provenance
with the model under test, and the top-level README repeats the caveat.

**Grader failures are not model failures.** A judge refusal, a judge outage or a crashing
grader marks the grade `error`; it is excluded from the pass rate, counted as a grader
error, and fails the gate with that reason. With `--no-judge`, LLM-rubric metrics are
reported as not evaluated rather than as 0%.

**A grader change does not need a paid rerun.** `--regrade <run-dir>` re-scores the saved
trajectories with the current graders and reuses the saved judge grades.

**Both directions are covered.** Each suite contains cases whose right answer is "absent",
"none", "cannot determine" or "fail", so a policy that always answers (or always passes)
cannot score well.

**Numbers carry intervals.** Pass rates are reported with 95% Wilson intervals, and
`--reps` repeats every case so run-to-run variance is visible. With 20 cases and one rep
the half-width is roughly ±20 points; the per-skill README states what the suite can and
cannot resolve.

**The judge is controlled.** The `llm_rubric` grader (`llm.py`) grades one property per
call with structured output, treats the candidate as untrusted data, is told not to reward
length, and is never told which answer is the reference. The judge model is a CLI flag;
the default is the same family as the model under test, which is a known self-preference
risk and is called out rather than hidden.

**Resumable, reproducible.** `--resume <run-dir>` skips completed `(case, rep)` pairs;
dependencies are locked (`uv.lock`); model IDs are exact strings; the committed
`latest/` directory of each skill holds the summary, report and raw rows of the last run.

## Reading a report

`evals/results/api/<skill>/latest/report.md` has, in order: counts (attempts, scored,
truncated, refusals, infrastructure errors), per-metric pass rate with interval and gate,
suite-level statistics (kappa, flip rate, ...), per-stratum breakdown, cost and latency,
per-attempt table, failure evidence, and infrastructure errors. `summary.json` holds the
same numbers for machines; `results.jsonl` and `errors.jsonl` are the raw rows.

## Running

```bash
uv sync
set CLAUDE_API_KEY=sk-ant-...            # or export on POSIX; ANTHROPIC_API_KEY also works

uv run evals/run.py --all --smoke        # free: oracle + null baseline
uv run evals/run.py --skill extract      # one skill, one rep
uv run evals/run.py --all --reps 2 --concurrency 4
uv run evals/run.py --skill judge --tag negative
uv run evals/run.py --skill adr --resume evals/results/api/adr/<timestamp>

claude plugin eval . --trust-plugin --no-publish --allow-tools Write --json evals/native/results/last.json
```
