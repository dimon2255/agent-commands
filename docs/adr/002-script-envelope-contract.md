# ADR 002: Skill scripts are subprocesses that emit one envelope

**Status:** Accepted, 2026-10-12

## Context

The harness needs usage, served model, stop reason and latency from every model call to
avoid the classic eval mistakes: estimating tokens from string length, scoring a clipped
answer as wrong, scoring an API error as a model failure, or reporting a number produced
by a different model than the one named. The three skills are written by different
builders in parallel and must plug into one runner.

## Decision

Every skill ships `scripts/<skill>.py`, a PEP 723 script that accepts
`--input <json> --json [--model] [--effort]` and prints exactly one JSON envelope
(`ok`, `output`, `error`, `meta{status, requested_model, served_model, usage, calls, latency_ms}`).
The harness runs it with `subprocess` in a thread pool, validates the envelope
(`evals/harness/contract.py`), and files anything that is not a scorable output into
`errors.jsonl` with a failure class. A reference implementation lives in
`evals/script_skeleton.py`.

Alternatives considered:

- *Import the skill as a module and call a function.* Faster, but the harness would then
  share a process, an SDK client and global state with the thing under test, and the
  eval would not exercise the real CLI entry point.
- *Have the harness make the API calls and the skill only supply prompts.* Simplest
  harness, but it moves the skill's logic (validation, repair loop, order swap) into the
  harness and the skill stops being a self-contained artifact.

## Consequences

- Positive: a skill can be exercised by hand with the same command the harness uses;
  contract violations fail loudly; scripts run anywhere `uv` runs.
- Negative: process start-up per attempt (hundreds of milliseconds), excluded from the
  reported model latency; a little duplicated tracking code across the three scripts.
