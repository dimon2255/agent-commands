# Progress

Portfolio repository: three Claude Code skills, each with an API-level eval suite and a
native `claude plugin eval` suite. Started 2026-10-12.

## Plan status

| Phase | Status | Notes |
|---|---|---|
| 1. Scaffold: plugin manifest, uv project, shared harness, docs | done 2026-10-12 | harness unit tests green |
| 2. Skill `extract` (schema-guided extraction, validate + repair) | in progress | |
| 3. Skill `judge` (rubric LLM-as-judge, calibration, position-bias control) | in progress | |
| 4. Skill `adr` (codebase-grounded ADR author, path hallucination check) | in progress | |
| 5. README, CI, license | pending | |
| 6. API evals run and recorded | pending | |
| 7. Native plugin evals run and recorded | pending | |
| 8. Independent review and fixes | pending | |
| 9. Public repo `dimon2255/agent-commands` | pending | |

## Decisions made during implementation

- ADR 001: one plugin, two eval layers (API-level harness + native `claude plugin eval`).
- ADR 002: every skill script emits the same envelope; the harness is the only consumer.
- Native eval cases grant only read-only tools plus `Skill`/`Write`: native Windows has no
  sandbox for `Bash`, so each SKILL.md documents an inline path that needs no script.
- Default model `claude-opus-5-5` for skills and for the judge. The judge model is a CLI
  flag because judging a model with itself invites self-preference; the README says so.

## Known issues

- None yet.
