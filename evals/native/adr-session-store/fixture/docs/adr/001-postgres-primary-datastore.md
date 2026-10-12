# ADR 001: Postgres 15 as the primary datastore

**Status:** Accepted, 2026-03-02

## Context

The shop needs relational data (orders, carts, customers) with transactions
across tables. The team has run Postgres in production for years.

## Decision

Use one managed Postgres 15 instance (`shop-db`, 4 vCPU, 16 GB RAM) for all
persistent data. Application code reaches it through SQLAlchemy.

## Consequences

- Positive: one backup, one failover procedure, one set of credentials.
- Negative: every feature competes for the same instance; heavy new workloads
  need a capacity check first. At the time of writing, p95 CPU is 35%.
