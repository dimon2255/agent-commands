# Eval report: `adr`

Generated 2026-10-12T17:36:58+00:00 · model `claude-opus-5-5` · judge `claude-opus-5-5` · effort `script default`

**Gate:** PASS

## Counts

| cases | reps | attempts | scored | truncated | refusals | infra errors | grader errors |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 2 | 20 | 20 | 0 | 0 | 0 | 0 |

## Metrics (scored attempts only)

| metric | n | pass rate | 95% CI | mean score | gate |
|---|---:|---:|---|---:|---|
| `sections_present` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 95.0% ✅ |
| `two_plus_alternatives` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 90.0% ✅ |
| `negative_consequence_present` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 90.0% ✅ |
| `paths_grounded` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 90.0% ✅ |
| `forbidden_path_absent` | 4 | 100.0% | [51.0%, 100.0%] | 1.000 |  |
| `number_correct` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 95.0% ✅ |
| `no_placeholders` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 100.0% ✅ |
| `constraints_named` | 12 | 100.0% | [75.8%, 100.0%] | 1.000 |  |
| `decision_fits_context` | 20 | 95.0% | [76.4%, 99.1%] | 0.938 | ≥ 80.0% ✅ |

## Suite-level statistics

| statistic | value |
|---|---|
| `unknown_paths_total` | 0 |
| `attempts_with_unknown_paths` | 0/20 |
| `mean_alternatives` | 3.25 |
| `mean_words` | 743 |
| `attempts_over_700_words` | 17/20 |

## By stratum (`tags[0]`)

| stratum | n | `sections_present` | `two_plus_alternatives` | `negative_consequence_present` | `paths_grounded` | `forbidden_path_absent` | `number_correct` | `no_placeholders` | `constraints_named` | `decision_fits_context` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api | 4 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| messaging | 4 | 100.0% | 100.0% | 100.0% | 100.0% | n/a | 100.0% | 100.0% | 100.0% | 100.0% |
| storage | 6 | 100.0% | 100.0% | 100.0% | 100.0% | n/a | 100.0% | 100.0% | 100.0% | 100.0% |
| tooling | 4 | 100.0% | 100.0% | 100.0% | 100.0% | n/a | 100.0% | 100.0% | 100.0% | 100.0% |
| tricky | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% |

## Cost and latency

- Skill cost: **$1.9952** total, $0.0998 per attempt
- Judge cost (recorded separately): **$0.3009**
- Model latency: p50 38019 ms, p95 64448 ms, mean 41128 ms (model-call time only; subprocess start-up, grading and retries excluded)
- Served model(s): `claude-opus-5-5`
- Refusal rate: 0.0%

## Per-attempt results

| case | rep | status | `sections_present` | `two_plus_alternatives` | `negative_consequence_present` | `paths_grounded` | `forbidden_path_absent` | `number_correct` | `no_placeholders` | `constraints_named` | `decision_fits_context` | cost | ms |
|---|---:|---|---|---|---|---|---|---|---|---|---|---:|---:|
| adr-api-pagination-thin-007 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0752 | 32391 |
| adr-api-pagination-thin-007 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0731 | 29904 |
| adr-api-versioning-006 | 1 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0.0991 | 40880 |
| adr-api-versioning-006 | 2 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0.0925 | 39859 |
| adr-messaging-job-queue-005 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0807 | 33591 |
| adr-messaging-job-queue-005 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0923 | 36800 |
| adr-messaging-outbox-004 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0878 | 33973 |
| adr-messaging-outbox-004 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0804 | 32598 |
| adr-storage-ledger-ids-003 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.1014 | 41454 |
| adr-storage-ledger-ids-003 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.1468 | 60389 |
| adr-storage-session-001 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0757 | 29514 |
| adr-storage-session-001 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0786 | 30809 |
| adr-storage-uploads-002 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0936 | 37163 |
| adr-storage-uploads-002 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0955 | 38019 |
| adr-tooling-ruff-009 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0974 | 39955 |
| adr-tooling-ruff-009 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.1047 | 41965 |
| adr-tooling-vitest-008 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.1239 | 51407 |
| adr-tooling-vitest-008 | 2 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.1029 | 42755 |
| adr-tricky-cache-decoy-010 | 1 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | 0.1481 | 64676 |
| adr-tricky-cache-decoy-010 | 2 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0.1455 | 64448 |

## Failure evidence

- `adr-tricky-cache-decoy-010` r1 `decision_fits_context`: judge score 2/5: Statements 2–4 hold: it identifies the local-only clear and the 300-second TTL, uses figures that match the context (1,800/s, 97%, 54 misses/s, pool 10, 200/day, 1gb), and treats pub/sub as not yet built. Statement 1 fails because the ADR admits that if the writing instance cannot p
