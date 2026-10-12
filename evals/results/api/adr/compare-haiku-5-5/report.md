# Eval report: `adr`

Generated 2026-10-12T17:21:15+00:00 · model `claude-haiku-5-5` · judge `claude-opus-5-5` · effort `script default`

**Gate:** PASS

## Counts

| cases | reps | attempts | scored | truncated | refusals | infra errors |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 1 | 10 | 9 | 1 | 0 | 0 |

## Metrics (scored attempts only)

| metric | n | pass rate | 95% CI | mean score | gate |
|---|---:|---:|---|---:|---|
| `sections_present` | 9 | 100.0% | [70.1%, 100.0%] | 1.000 | ≥ 95.0% ✅ |
| `two_plus_alternatives` | 9 | 100.0% | [70.1%, 100.0%] | 1.000 | ≥ 90.0% ✅ |
| `negative_consequence_present` | 9 | 100.0% | [70.1%, 100.0%] | 1.000 | ≥ 90.0% ✅ |
| `paths_grounded` | 9 | 100.0% | [70.1%, 100.0%] | 1.000 | ≥ 90.0% ✅ |
| `forbidden_path_absent` | 1 | 100.0% | [20.6%, 100.0%] | 1.000 |  |
| `number_correct` | 9 | 100.0% | [70.1%, 100.0%] | 1.000 | ≥ 95.0% ✅ |
| `no_placeholders` | 9 | 100.0% | [70.1%, 100.0%] | 1.000 | ≥ 100.0% ✅ |
| `constraints_named` | 5 | 100.0% | [56.5%, 100.0%] | 1.000 |  |
| `decision_fits_context` | 9 | 100.0% | [70.1%, 100.0%] | 0.917 |  |

## Suite-level statistics

| statistic | value |
|---|---|
| `unknown_paths_total` | 0 |
| `attempts_with_unknown_paths` | 0/9 |
| `mean_alternatives` | 3.44 |
| `mean_words` | 680 |
| `attempts_over_700_words` | 3/9 |

## By stratum (`tags[0]`)

| stratum | n | `sections_present` | `two_plus_alternatives` | `negative_consequence_present` | `paths_grounded` | `forbidden_path_absent` | `number_correct` | `no_placeholders` | `constraints_named` | `decision_fits_context` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| messaging | 2 | 100.0% | 100.0% | 100.0% | 100.0% | n/a | 100.0% | 100.0% | 100.0% | 100.0% |
| storage | 3 | 100.0% | 100.0% | 100.0% | 100.0% | n/a | 100.0% | 100.0% | 100.0% | 100.0% |
| tooling | 2 | 100.0% | 100.0% | 100.0% | 100.0% | n/a | 100.0% | 100.0% | 100.0% | 100.0% |

## Cost and latency

- Skill cost: **$0.061** total, $0.0061 per attempt
- Judge cost (recorded separately): **$0.1583**
- Model latency: p50 46307 ms, p95 72421 ms, mean 48642 ms (model-call time only; subprocess start-up, grading and retries excluded)
- Served model(s): `claude-haiku-5-5`
- Refusal rate: 0.0%

## Per-attempt results

| case | rep | status | `sections_present` | `two_plus_alternatives` | `negative_consequence_present` | `paths_grounded` | `forbidden_path_absent` | `number_correct` | `no_placeholders` | `constraints_named` | `decision_fits_context` | cost | ms |
|---|---:|---|---|---|---|---|---|---|---|---|---|---:|---:|
| adr-api-pagination-thin-007 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0050 | 40339 |
| adr-api-versioning-006 | 1 | ok | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 0.0068 | 54480 |
| adr-messaging-job-queue-005 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0067 | 52733 |
| adr-messaging-outbox-004 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0040 | 30403 |
| adr-storage-ledger-ids-003 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0077 | 61083 |
| adr-storage-session-001 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0045 | 35730 |
| adr-storage-uploads-002 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0057 | 46307 |
| adr-tooling-ruff-009 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | n/a | ✅ | 0.0045 | 33493 |
| adr-tooling-vitest-008 | 1 | ok | ✅ | ✅ | ✅ | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | 0.0078 | 59427 |
| adr-tricky-cache-decoy-010 | 1 | truncated | — | — | — | — | — | — | — | — | — | 0.0083 | 72421 |
