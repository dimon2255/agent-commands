# invoicing-service

Creates customer invoices and sends the nightly invoice export to the external accountant.

## Runtime

- Two replicas of the API container on the shared Kubernetes cluster (config/app.yaml).
- Postgres 16 is the system of record (ADR 001).

## Infrastructure policy (2026-Q4)

No new infrastructure this quarter. Only the existing Postgres 16 database and the existing
application containers may be used: no Redis, no message brokers, no new managed services.
Requests for new services reopen in January 2027.

## Nightly invoice export

The export (src/invoicing/export.py) must run once per night after 01:00 UTC. Today the
on-call engineer starts it by hand in one of the API containers. It was missed on 9 of the
last 30 nights, and the accountant chased the missing files each time.
