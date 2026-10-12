# Progress

Portfolio repository: three Claude Code skills, each with an API-level eval suite and a
native `claude plugin eval` suite. Started 2026-10-12.

## Plan status

| Phase | Status | Notes |
|---|---|---|
| 1. Scaffold: plugin manifest, uv project, shared harness, docs | done 2026-10-12 | 21 harness tests on a fake-skill fixture |
| 2. Skill `extract` (schema-guided extraction, validate + repair) | done 2026-10-12 | 20 cases, 24 unit tests; labels independently re-verified |
| 3. Skill `judge` (rubric LLM-as-judge, calibration, position-bias control) | done 2026-10-12 | 34 cases, 46 unit tests; labels independently re-verified |
| 4. Skill `adr` (codebase-grounded ADR author, path hallucination check) | in progress | |
| 5. README, CI, license | done 2026-10-12 | results table filled per run |
| 6. API evals run and recorded | extract, judge done; adr pending | 2 reps each + Haiku 5.5 comparison |
| 7. Native plugin evals run and recorded | extract, judge cases pass; full run pending | rubric graders corrected once (see decisions) |
| 8. Independent review and fixes | pending | |
| 9. Public repo `dimon2255/agent-commands` | pending | |

## Decisions made during implementation

- ADR 001: one plugin, two eval layers (API-level harness + native `claude plugin eval`).
- ADR 002: every skill script emits the same envelope; the harness is the only consumer.
- ADR 003: relax the user's schema for the structured-output grammar, validate the full
  schema in Python, one bounded repair pass.
- Native eval cases grant only read-only tools plus `Skill`/`Write`: native Windows has no
  sandbox for `Bash`, so each SKILL.md documents an inline path that needs no script.
- Default model `claude-opus-5-5` for skills and for the judge. The judge model is a CLI
  flag because judging a model with itself invites self-preference; the README says so.
- Labels: the case sets were drafted by builder agents running on `claude-opus-5-5`, the
  model under test. Every label was then independently re-derived by a different model
  (`claude-fable-5-1`) and recorded as `label_verified_by` on each case. A second human
  labeller is still the right next step for the borderline judge items.
- `uv` link mode is `copy` (pyproject `[tool.uv]`): `claude plugin eval` refuses a plugin
  tree with hard-linked files, and uv hard-links packages into `.venv` by default.
- Native rubric graders judge the extracted *values*, not evidence quotes; the first
  version of the extract rubric failed the plugin arm for a currency symbol inside a
  verbatim quote (a grader bug, fixed 2026-10-12).

## Known issues and hardening backlog

- Both finished API suites are saturated: `claude-opus-5-5` and `claude-haiku-5-5` pass
  every case. They are regression guards and cost baselines, not model rankers. To open a
  gap: OCR-noisy and multi-page documents, nested schemas with arrays of objects,
  conflicting values (two totals that both claim to be final), borderline judge items
  labelled by a second person, pairwise items where the longer answer is correct.
- The `extract` repair path has never been triggered by a real validation error in a live
  run (0 of 60 attempts); it is covered by fake-client tests and one forced live call.
- `claude plugin eval` on native Windows cannot grant `Bash`, so the native cases exercise
  the inline paths only; the script paths are covered by the API-level suites.
