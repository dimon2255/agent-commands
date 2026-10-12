# Eval report: `judge`

Generated 2026-10-12T16:55:05+00:00 · model `claude-opus-5-5` · judge `none` · effort `script default`

**Gate:** PASS

## Counts

| cases | reps | attempts | scored | truncated | refusals | infra errors |
|---:|---:|---:|---:|---:|---:|---:|
| 34 | 2 | 68 | 68 | 0 | 0 | 0 |

## Metrics (scored attempts only)

| metric | n | pass rate | 95% CI | mean score | gate |
|---|---:|---:|---|---:|---|
| `agrees_with_human` | 48 | 100.0% | [92.6%, 100.0%] | 1.000 | ≥ 85.0% ✅ |
| `score_within_one` | 48 | 100.0% | [92.6%, 100.0%] | 1.000 |  |
| `picks_correct_winner` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 80.0% ✅ |
| `position_consistent` | 20 | 100.0% | [83.9%, 100.0%] | 1.000 | ≥ 80.0% ✅ |
| `known_negative_fails` | 8 | 100.0% | [67.6%, 100.0%] | 1.000 | ≥ 100.0% ✅ |
| `criteria_have_evidence` | 46 | 100.0% | [92.3%, 100.0%] | 1.000 |  |

## Suite-level statistics

| statistic | value |
|---|---|
| `pointwise_n` | 48 |
| `agreement` | 1.0 |
| `agreement_clear_cut` | 1.0 |
| `n_clear_cut` | 28 |
| `agreement_borderline` | 1.0 |
| `n_borderline` | 12 |
| `agreement_known_negative` | 1.0 |
| `n_known_negative` | 8 |
| `majority_class_baseline` | 0.583 |
| `cohen_kappa_pass_fail` | 1.0 |
| `weighted_kappa_score_1_5` | 0.979 |
| `judge_pass_rate` | 0.417 |
| `human_pass_rate` | 0.417 |
| `pairwise_n` | 20 |
| `position_flip_rate` | 0.0 |

## By stratum (`tags[0]`)

| stratum | n | `agrees_with_human` | `score_within_one` | `picks_correct_winner` | `position_consistent` | `known_negative_fails` | `criteria_have_evidence` |
|---|---:|---:|---:|---:|---:|---:|---:|
| negative | 8 | 100.0% | 100.0% | n/a | n/a | 100.0% | 100.0% |
| pairwise | 20 | n/a | n/a | 100.0% | 100.0% | n/a | n/a |
| pointwise | 40 | 100.0% | 100.0% | n/a | n/a | n/a | 100.0% |

## Cost and latency

- Skill cost: **$1.389** total, $0.0204 per attempt
- Judge cost (recorded separately): **$0.0**
- Model latency: p50 5927 ms, p95 9251 ms, mean 5899 ms (model-call time only; subprocess start-up, grading and retries excluded)
- Served model(s): `claude-opus-5-5`
- Refusal rate: 0.0%

## Per-attempt results

| case | rep | status | `agrees_with_human` | `score_within_one` | `picks_correct_winner` | `position_consistent` | `known_negative_fails` | `criteria_have_evidence` | cost | ms |
|---|---:|---|---|---|---|---|---|---|---:|---:|
| judge-neg-empty | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | n/a | 0.0114 | 2845 |
| judge-neg-empty | 2 | ok | ✅ | ✅ | n/a | n/a | ✅ | n/a | 0.0118 | 2583 |
| judge-neg-idk | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0123 | 2902 |
| judge-neg-idk | 2 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0133 | 3525 |
| judge-neg-injection | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0139 | 3727 |
| judge-neg-injection | 2 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0143 | 4077 |
| judge-neg-wrong-question | 1 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0161 | 4317 |
| judge-neg-wrong-question | 2 | ok | ✅ | ✅ | n/a | n/a | ✅ | ✅ | 0.0148 | 3914 |
| judge-pair-review-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0317 | 10685 |
| judge-pair-review-01 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0317 | 10630 |
| judge-pair-review-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0291 | 8284 |
| judge-pair-review-02 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0286 | 7613 |
| judge-pair-sql-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0334 | 8031 |
| judge-pair-sql-01 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0339 | 8335 |
| judge-pair-sql-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0309 | 7480 |
| judge-pair-sql-02 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0310 | 7970 |
| judge-pair-sql-03 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0329 | 7744 |
| judge-pair-sql-03 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0332 | 7778 |
| judge-pair-summary-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0320 | 7781 |
| judge-pair-summary-01 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0318 | 7462 |
| judge-pair-summary-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0319 | 8517 |
| judge-pair-summary-02 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0318 | 8259 |
| judge-pair-support-01 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0300 | 9251 |
| judge-pair-support-01 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0305 | 7902 |
| judge-pair-support-02 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0272 | 7144 |
| judge-pair-support-02 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0276 | 7037 |
| judge-pair-support-03 | 1 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0264 | 8115 |
| judge-pair-support-03 | 2 | ok | n/a | n/a | ✅ | ✅ | n/a | n/a | 0.0263 | 7820 |
| judge-point-review-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0173 | 5927 |
| judge-point-review-01 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0175 | 6291 |
| judge-point-review-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0195 | 6180 |
| judge-point-review-02 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0229 | 8377 |
| judge-point-review-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0149 | 9500 |
| judge-point-review-03 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0144 | 4169 |
| judge-point-review-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0138 | 4092 |
| judge-point-review-04 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0133 | 3781 |
| judge-point-review-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0185 | 5999 |
| judge-point-review-05 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0193 | 5813 |
| judge-point-sql-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0162 | 4034 |
| judge-point-sql-01 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0168 | 4359 |
| judge-point-sql-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0151 | 6018 |
| judge-point-sql-02 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0152 | 6406 |
| judge-point-sql-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0232 | 7642 |
| judge-point-sql-03 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0209 | 6250 |
| judge-point-sql-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0155 | 4133 |
| judge-point-sql-04 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0158 | 4347 |
| judge-point-sql-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0152 | 4620 |
| judge-point-sql-05 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0152 | 4637 |
| judge-point-summary-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0149 | 4143 |
| judge-point-summary-01 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0144 | 3620 |
| judge-point-summary-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0144 | 3916 |
| judge-point-summary-02 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0146 | 3905 |
| judge-point-summary-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0148 | 4137 |
| judge-point-summary-03 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0146 | 3900 |
| judge-point-summary-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0140 | 3204 |
| judge-point-summary-04 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0142 | 3362 |
| judge-point-summary-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0195 | 7282 |
| judge-point-summary-05 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0190 | 6357 |
| judge-point-support-01 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0220 | 7865 |
| judge-point-support-01 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0188 | 5925 |
| judge-point-support-02 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0153 | 3991 |
| judge-point-support-02 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0150 | 3911 |
| judge-point-support-03 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0139 | 3756 |
| judge-point-support-03 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0137 | 3328 |
| judge-point-support-04 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0197 | 6323 |
| judge-point-support-04 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0192 | 6196 |
| judge-point-support-05 | 1 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0183 | 5864 |
| judge-point-support-05 | 2 | ok | ✅ | ✅ | n/a | n/a | n/a | ✅ | 0.0184 | 5829 |
