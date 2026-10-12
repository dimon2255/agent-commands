---
type: llm
weight: 2
focus: { source: file, path: "docs/adr/002-nightly-invoice-export.md" }
---
The candidate is a decision record written about a small repository whose only files are:
README.md, config/app.yaml, src/invoicing/export.py, src/invoicing/db.py,
docs/adr/001-postgres-system-of-record.md. Paths appear relative to that repository root
(for example `src/invoicing/export.py`). The README states a policy: no new infrastructure
this quarter; only the existing Postgres database and the existing application containers
may be used.

PASS if all of these hold: the record does not choose Celery, Redis or any other new service,
and rejects Celery with Redis because of the no-new-infrastructure policy; the chosen approach
uses only the existing Postgres database and application containers, and says how the export
is kept from running twice across the two replicas (for example a Postgres advisory lock, a
job-run table, or a single scheduled run with overlapping runs forbidden); it cites at least
one of the files above by path; it lists two or more alternatives with a reason for rejecting
each; and it names at least one concrete negative consequence of the chosen option.
FAIL if any of these does not hold, or if any cited file path is not in the list above (the
record's own path excepted).
