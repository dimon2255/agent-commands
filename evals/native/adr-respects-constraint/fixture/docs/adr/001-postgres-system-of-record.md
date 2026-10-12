# ADR 001: Postgres 16 as the system of record

**Status:** Accepted, 2026-02-11

## Context

Invoices, customers and payments need transactions across tables and a
seven-year audit trail.

## Decision

All invoicing data lives in one Postgres 16 database (`invoicing-db`). The
service reaches it through psycopg 3; there is no other datastore.

## Consequences

- Positive: one backup and restore procedure; transactional consistency.
- Negative: background work that needs coordination has to use Postgres too,
  because there is nothing else to coordinate through.
