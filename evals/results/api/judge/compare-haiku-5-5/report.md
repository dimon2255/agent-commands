# Eval report: `judge`

Generated 2026-10-12T16:54:53+00:00 · model `claude-haiku-5-5` · judge `none` · effort `script default`

**Gate:** PASS

## Counts

| cases | reps | attempts | scored | truncated | refusals | infra errors |
|---:|---:|---:|---:|---:|---:|---:|
| 34 | 1 | 34 | 34 | 0 | 0 | 0 |

## Metrics (scored attempts only)

| metric | n | pass rate | 95% CI | mean score | gate |
|---|---:|---:|---|---:|---|
| `agrees_with_human` | 24 | 100.0% | [86.2%, 100.0%] | 1.000 | ≥ 85.0% ✅ |
| `score_within_one` | 24 | 100.0% | [86.2%, 100.0%] | 1.000 |  |
| `picks_correct_winner` | 10 | 100.0% | [72.2%, 100.0%] | 1.000 | ≥ 80.0% ✅ |
| `position_consistent` | 10 | 100.0% | [72.2%, 100.0%] | 1.000 | ≥ 80.0% ✅ |
| `known_negative_fails` | 4 | 100.0% | [51.0%, 100.0%] | 1.000 | ≥ 100.0% ✅ |
| `criteria_have_evidence` | 23 | 100.0% | [85.7%, 100.0%] | 1.000 |  |

## Suite-level statistics

| statistic | value |
|---|---|
| `pointwise_n` | 24 |
| `agreement` | 1.0 |
| `agreement_clear_cut` | 1.0 |
| `n_clear_cut` | 14 |
| `agreement_borderline` | 1.0 |
| `n_borderline` | 6 |
| `agreement_known_negative` | 1.0 |
| `n_known_negative` | 4 |
| `majority_class_baseline` | 0.583 |
| `cohen_kappa_pass_fail` | 1.0 |
| `weighted_kappa_score_1_5` | 0.959 |
| `judge_pass_rate` | 0.417 |
| `human_pass_rate` | 0.417 |
| `pairwise_n` | 10 |
| `position_flip_rate` | 0.0 |

## By stratum (`tags[0]`)

| stratum | n | `agrees_with_human` | `score_within_one` | `picks_correct_winner` | `position_consistent` | `known_negative_fails` | `criteria_have_evidence` |
|---|---:|---:|---:|---:|---:|---:|---:|
| negative | 4 | 100.0% | 100.0% | n/a | n/a | 100.0% | 100.0% |
| pairwise | 10 | n/a | n/a | 100.0% | 100.0% | n/a | n/a |
| pointwise | 20 | 100.0% | 100.0% | n/a | n/a | n/a | 100.0% |

## Cost and latency

- Skill cost: **$0.0205** total, $0.0006 per attempt
- Judge cost (recorded separately): **$0.0**
- Model latency: p50 3668 ms, p95 6867 ms, mean 4064 ms (model-call time only; subprocess start-up, grading and retries excluded)
- Served model(s): `claude-haiku-5-5`
- Refusal rate: 0.0%

## Per-attempt results

| case | rep | status | `agrees_with_human` | `score_within_one` | `picks_correct_winner` | `position_consistent` | `known_negative_fails` | `criteria_have_evidence` | cost | ms |
|---|---:|---|---|---|---|---|---|---|---:|---:|
| judge-neg-empty | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | n/a | 0.0003 | 2533 |
| judge-neg-idk | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0003 | 2240 |
| judge-neg-injection | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0004 | 3111 |
| judge-neg-wrong-question | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0004 | 2675 |
| judge-pair-review-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0008 | 4808 |
| judge-pair-review-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0010 | 6434 |
| judge-pair-sql-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0008 | 4339 |
| judge-pair-sql-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0009 | 6116 |
| judge-pair-sql-03 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0007 | 4501 |
| judge-pair-summary-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0014 | 9425 |
| judge-pair-summary-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0009 | 6019 |
| judge-pair-support-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0008 | 4909 |
| judge-pair-support-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0009 | 5786 |
| judge-pair-support-03 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0010 | 6867 |
| judge-point-review-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0006 | 4694 |
| judge-point-review-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0006 | 4289 |
| judge-point-review-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2906 |
| judge-point-review-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0005 | 4042 |
| judge-point-review-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0006 | 4763 |
| judge-point-sql-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2567 |
| judge-point-sql-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2782 |
| judge-point-sql-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2607 |
| judge-point-sql-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2570 |
| judge-point-sql-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2805 |
| judge-point-summary-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2683 |
| judge-point-summary-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0005 | 3363 |
| judge-point-summary-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0006 | 4277 |
| judge-point-summary-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2572 |
| judge-point-summary-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0006 | 4665 |
| judge-point-support-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0005 | 3507 |
| judge-point-support-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2953 |
| judge-point-support-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0004 | 2462 |
| judge-point-support-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0006 | 4240 |
| judge-point-support-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0005 | 3668 |
