---
name: adr
description: Write an Architecture Decision Record grounded in the actual codebase. Reads the files a decision touches, then records the context (citing only files it opened), the decision, at least two rejected alternatives with reasons, and concrete positive and negative consequences, numbered after the repository's existing ADRs. Use whenever the user says "write an ADR", "document this decision", "record this decision", "decision record", "we decided to use X, record it", "architecture decision", "why did we choose X", or asks to choose between two technologies, libraries or approaches (Redis or Postgres, REST or gRPC, Jest or Vitest, a queue or a cron job), or wants any design trade-off put on record for the team, even when nobody says "ADR".
argument-hint: "<decision> [--constraint ...]"
allowed-tools: Read, Glob, Grep, Write
---

# ADR: decision records grounded in the code

An ADR that cites files nobody opened, or lists only benefits, is worse than no ADR: it
gives the next reader false confidence. This skill reads first and writes second, and
every path it cites is a file it opened.

Request: $ARGUMENTS

## Procedure

### 1. Restate the decision as one question

Write the decision as a single question with the options in it, for example "Where should
web session state live now that the API runs three replicas: Redis, Postgres, or sticky
sessions?". If the user already decided ("we chose X, record it"), the question is still
"which option, and why", and the record documents why X won. If the files you read
contradict X, say so in the record; do not quietly pick a different winner, and do not
hide the problem.

If the user named a path for the record, use it. Otherwise continue with step 2.

### 2. Find the ADR directory and the next number

Glob, in this order: `docs/adr/*.md`, `doc/adr/*.md`, `adr/*.md`, `docs/decisions/*.md`,
`docs/architecture/decisions/*.md`. Use the first directory that has files named
`NNN-slug.md`.

- Next number = highest leading number + 1, zero-padded to three digits. Never reuse a
  number, even when there are gaps.
- No ADR directory: use `docs/adr/` and number 001.
- Read the titles of the existing records. Open any record this decision supersedes,
  depends on, or contradicts; it belongs in the context pack.

### 3. Gather the context pack

Use Grep and Glob to find the files the decision touches, then Read each one in full
before relying on it:

- the module in question and its main callers;
- configuration that states the facts (replica counts, pools, timeouts, feature flags);
- infrastructure definitions (Terraform, Kubernetes, compose files, CI workflows);
- README sections, runbooks, incident notes, capacity or metrics notes;
- dependency manifests when the decision is about a library or tool;
- the existing ADRs found in step 2 that relate to this decision.

Keep the pack to about 15 files. Prefer the file that states a fact over a file that
repeats it. Keep a list of the files you opened: these, and only these, may be cited.

Collect the constraints: those the user gave (`--constraint ...`) and those the files
state (for example "no new infrastructure this quarter", a retention rule, a partner
contract). Write each one down; the record must name every one.

Documents go stale. Before citing a path that a README or design note mentions, Glob for
it. If it does not exist, do not cite it; describe the discrepancy in words ("the
architecture notes name a cache module that no longer exists").

### 4. Draft the record

**Script path** (a shell is available, `uv` is installed, and `CLAUDE_API_KEY` or
`ANTHROPIC_API_KEY` is set):

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/adr.py" \
  --decision "<the question from step 1>" \
  --context <file> --context <file> \
  --constraint "<each constraint>" \
  --adr-dir <adr directory> --write
```

The script makes one structured model call, numbers the record from the ADR directory,
checks every path-like token in the draft against the files you passed, and prints the
record followed by `cited paths`, `unknown paths` and `warnings`. It writes
`<adr-dir>/NNN-slug.md` only when no unknown path is cited. When it reports unknown paths
or warnings, fix the draft yourself and write it with the inline path; never add a file
to `--context` just to make a path known. If the script cannot run (no key, no `uv`, a
network or API error), do not retry in a loop: use the inline path.

**Inline path** (no shell, or the script failed): write the record yourself with the
house template below (full template and a filled example in
[references/adr-template.md](references/adr-template.md)). Rules:

1. Cite files by repository-relative path in backticks, only files you opened. Never cite
   a path that is missing, stale, or that the decision would create; describe those in
   words.
2. Refer to other records as "ADR 001" plus their title.
3. Name each constraint in Context, and say in Decision how the decision satisfies it. A
   constraint can rule out the option that would otherwise win; say so when it does.
4. At least two alternatives, as a bullet list, each with the concrete reason it was
   rejected. They must be options a competent engineer on this codebase would propose.
5. Consequences as a `Positive:` list and a `Negative:` list. At least one negative, and
   every negative concrete: a cost, a risk or an operational burden in this codebase.
6. Thin evidence: say in Context what the files do not show, list your assumptions,
   decide anyway, and name the measurement or event that would reopen the decision.
7. Status `Proposed` with today's date. No TBD, TODO or placeholder text. No marketing
   language. Under about 700 words.

Then Write the record to `<adr-dir>/NNN-slug.md` (slug: kebab-case, at most six words).

### 5. Check before you finish

- Every backticked path is a file you opened in step 3.
- The number is the next free number, and the heading matches the file name.
- The five parts are present: title, Context, Decision, Alternatives considered,
  Consequences.
- Two or more alternatives, each with a reason; at least one concrete negative.
- Each constraint is named; no TBD, TODO or placeholder.

### 6. Report

Print the path of the record, then a three-line summary:

```
Decision: <one sentence>
Rejected: <strongest alternative> because <reason>
Cost: <the most important negative consequence>
```

### 7. Progress log

If `docs/PROGRESS.md` exists and has a decisions section (a heading that contains
"Decision"), append one line under it:
`- ADR NNN: <title> (docs/adr/NNN-slug.md)`. Do not create the file or the section.

## House template

```markdown
# ADR NNN: <Decision as a short phrase>

**Status:** Proposed, YYYY-MM-DD

## Context

<The problem and the facts that force a decision, each tied to a cited file.
Constraints, named. What the files do not show, and the assumptions made.>

## Decision

<What we will do, specifically enough to implement and review. How each constraint
is satisfied.>

## Alternatives considered

- <Alternative>: rejected because <concrete reason in this codebase>.
- <Alternative>: rejected because <concrete reason>.

## Consequences

Positive:

- <What becomes easier or safer.>

Negative:

- <What becomes harder, costlier or riskier, concretely.>

## Follow-ups

- <Optional: work this decision creates.>
```

## Short example

> **Context.** `src/session.py` keeps sessions in a process-local dictionary, and
> `config/app.yaml` runs three replicas behind a round-robin load balancer. Constraint: no
> new infrastructure this quarter (`README.md`).
>
> **Decision.** Store sessions in a table in the existing Postgres instance; this uses
> only infrastructure we already run.
>
> **Alternatives.** Redis: rejected because it is new infrastructure, which the
> constraint forbids. Sticky sessions: rejected because rolling deploys still drop them.
>
> **Negative.** About 340 extra database reads per second at peak, and expired rows need
> a cleanup job.

## Do not

- Cite a path you did not open, or one a document mentions that Glob cannot find.
- Write TBD, TODO or placeholder text. Decide now under stated assumptions instead.
- List alternatives for show. Each alternative is a real option with the reason it lost.
- Write a record that lists only benefits.
- Edit an accepted record to change its decision. Write a new record that supersedes it,
  and say which one it supersedes.
