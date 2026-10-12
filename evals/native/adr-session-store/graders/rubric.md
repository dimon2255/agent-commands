---
type: llm
weight: 2
focus: { source: file, path: "docs/decisions/002-session-state-store.md" }
---
The candidate is a decision record written about a small repository whose only files are:
README.md, config/app.yaml, src/app.py, src/session.py, docs/adr/001-postgres-primary-datastore.md.
Paths may appear relative to that repository root (for example `src/session.py`) or with a
`fixture/` prefix; both count as the same file.

PASS if the record cites at least one of those files by path, moves session state out of
process memory into a store shared by all replicas, lists two or more alternatives with a
reason for rejecting each, and names at least one concrete negative consequence of the
chosen option. FAIL if any cited file path is not in the list above (the record's own path
excepted), alternatives are missing or have no reasons, or only benefits are listed.
