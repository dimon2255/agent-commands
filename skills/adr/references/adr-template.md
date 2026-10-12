# ADR template and a filled example

The house format is MADR-flavoured and matches `docs/adr/` in this repository. The title
names the decision, not the problem. Every path in backticks is a file the author opened.

## Template

```markdown
# ADR NNN: <Decision as a short phrase>

**Status:** Proposed, YYYY-MM-DD

## Context

<The forces: what is happening, which facts make a decision necessary, each tied to a
cited file. Constraints, each named. What the files do not show, and the assumptions.>

## Decision

<What we will do, specifically enough to implement and review. How each constraint is
satisfied. What would make us reopen this decision, if anything.>

## Alternatives considered

- <Alternative>: rejected because <concrete reason in this codebase>.
- <Alternative>: rejected because <concrete reason>.

## Consequences

Positive:

- <What becomes easier, safer or cheaper.>

Negative:

- <What becomes harder, costlier or riskier. Name the cost, not a category.>

## Follow-ups

- <Optional: concrete work this decision creates.>
```

Status values: `Proposed`, `Accepted`, `Deprecated`, `Superseded by ADR NNN`.

## Filled example

```markdown
# ADR 002: Store web sessions in Postgres

**Status:** Proposed, 2026-10-12

## Context

`src/session.py` keeps sessions in a process-local dictionary, and `config/app.yaml` runs
three replicas behind a round-robin load balancer with session affinity off, so a request
that reaches another replica gets a 401. Sessions must stay revocable per user, which
needs server-side state.

Constraint: no new infrastructure this quarter; only the managed Postgres 15 instance and
the load balancer may be used (`README.md`). ADR 001 makes that instance the primary
datastore.

## Decision

Move sessions into a sessions table in the existing Postgres instance, keyed by session
ID, indexed by user ID and expiry. Refresh the sliding expiry at most every five minutes.
This uses only infrastructure we already run, which satisfies the constraint.

## Alternatives considered

- Redis as a session store: rejected because it is new infrastructure, which the
  constraint forbids this quarter.
- Sticky sessions through cookie affinity: rejected because the rolling deploy replaces
  one replica at a time, so deploys would still log users out.
- Stateless signed cookies: rejected because per-user revocation needs server-side state.

## Consequences

Positive:

- Every replica sees the same sessions, so random logouts stop.

Negative:

- Postgres takes about 340 extra primary-key reads per second at peak.
- Expired rows need a cleanup job, and the table bloats if that job stops.
```
