# Progress

Portfolio repository: three Claude Code skills, each with an API-level eval suite and a
native `claude plugin eval` suite. Built 2026-10-12.

## Plan status

| Phase | Status | Notes |
|---|---|---|
| 1. Scaffold: plugin manifest, uv project, shared harness, docs | done 2026-10-12 | harness tests on a fake-skill fixture |
| 2. Skill `extract` (schema-guided extraction, validate + repair) | done 2026-10-12 | 20 cases; labels independently re-derived |
| 3. Skill `judge` (rubric LLM-as-judge, calibration, position-bias control) | done 2026-10-12 | 34 cases; labels independently re-derived |
| 4. Skill `adr` (codebase-grounded ADR author, path hallucination check) | done 2026-10-12 | 10 cases; labels independently re-derived |
| 5. README, CI, license | done 2026-10-12 | results tables filled from committed summaries |
| 6. API evals run and recorded | done 2026-10-12 | 2 reps per skill + Haiku 5.5 comparison; `latest/` committed |
| 7. Native plugin evals run and recorded | done 2026-10-12 | 6 cases, two arms, `evals/native/latest.json` + `RESULTS.md` |
| 8. Independent review and fixes | done 2026-10-12 | REQUEST_CHANGES with 3 blockers + 2 must-fix; all addressed, 134 tests |
| 9. Public repo `dimon2255/agent-commands` | done 2026-10-12 | CI on push; API evals on dispatch with `CLAUDE_API_KEY` secret |
| 10. API evals reproduced in GitHub Actions | done 2026-10-12 | dispatch run 38292791709: 1 rep, every gate passed, `adr` judge 8/10 at the 0.80 gate, 0 infra errors, $2.10 |

## Decisions made during implementation

- ADR 001: one plugin, two eval layers (API-level harness + native `claude plugin eval`).
- ADR 002: every skill script emits the same envelope; the harness is the only consumer.
- ADR 003: relax the user's schema for the structured-output grammar, validate the full
  schema in Python, one bounded repair pass.
- Native eval cases grant only read-only tools plus `Skill`/`Write`: native Windows has no
  sandbox for `Bash`, so each SKILL.md documents an inline path that needs no script. The
  `adr` cases inline their small repositories because the agent cannot see a directory
  granted through `context.add_dirs` in the empty eval workspace.
- Default model `claude-opus-5-5` for skills and for the judge. The judge model is a CLI
  flag because judging a model with itself invites self-preference; the README says so.
- Labels: the case sets were drafted by builder agents running on `claude-opus-5-5`, the
  model under test. Every label was then independently re-derived by a different model
  (`claude-fable-5-1`) and recorded as `label_verified_by` on each case; two gold values
  and one over-strict rubric were corrected. A second human labeller is still the right
  next step for the borderline judge items.
- Grader failures (judge refusal or outage, crashing grader) are their own class: excluded
  from pass rates, counted, and they fail the gate with a reason. A grader change is
  applied to a saved run with `--regrade`, not by paying for a rerun.
- `uv` link mode is `copy` (pyproject `[tool.uv]`): `claude plugin eval` refuses a plugin
  tree with hard-linked files, and uv hard-links packages into `.venv` by default.
- Native rubric graders judge the extracted *values*, not evidence quotes; the first
  version of the extract rubric failed the plugin arm for a currency symbol inside a
  verbatim quote (a grader bug, fixed 2026-10-12).
- Grader bugs found by the live runs and fixed with `--regrade`: a bare extension in prose
  ("the `.js` module mapper") counted as a hallucinated path; a boolean answered `False`
  for a silent text was asked for an evidence quote.
- Commits use the GitHub noreply address; history was rewritten before the first push.

## Known issues and hardening backlog

- The API suites are saturated: `claude-opus-5-5` and `claude-haiku-5-5` pass every
  `extract` and `judge` case, and differ on `adr` only by one truncated Haiku attempt.
  They are regression guards and cost baselines, not model rankers. To open a gap:
  OCR-noisy and multi-page documents, nested schemas with arrays of objects, conflicting
  values (two totals that both claim to be final), borderline judge items labelled by a
  second person, pairwise items where the longer answer is correct, ADR packs with
  contradictory files.
- `adr` records run long: 17 of 20 attempts exceeded the 700-word target (mean 743).
- The `extract` repair path has never been triggered by a real validation error in a live
  run (0 of 80 attempts); it is covered by fake-client tests and one forced live call.
- The native `extract-ticket-missing-field` case has a flaky LLM rubric vote (1 of 2
  with-plugin runs); the deterministic graders pass in every run.
- `claude plugin eval` on native Windows cannot grant `Bash`, so the native cases exercise
  the inline paths only; the script paths are covered by the API-level suites.
