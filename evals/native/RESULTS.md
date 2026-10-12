# Native eval results (claude plugin eval)

Run 2026-10-12T17:36:14Z · Claude Code 2.1.296 · ablation with-without · 2 runs per case per arm · 225 s · subscription cost $2.89

Command: `claude plugin eval . --trust-plugin --no-publish --allow-tools Write -j 3 --json evals/native/latest.json`
(run against a copy of the repository without `.venv`; see README).

**Overall:** 5/6 cases passed at threshold 1.0 · mean score with plugin 0.97 · mean delta over no-plugin +0.22

| case | with plugin (2 runs) | without plugin (2 runs) | delta | skill fired |
|---|---|---|---:|---|
| `adr-respects-constraint` | 1.00, 1.00 | 1.00, 1.00 | +0.00 | 2/2 |
| `adr-session-store` | 1.00, 1.00 | 0.80, 0.80 | +0.20 | 2/2 |
| `extract-invoice-inline` | 1.00, 1.00 | 1.00, 1.00 | +0.00 | 2/2 |
| `extract-ticket-missing-field` | 1.00, 0.60 | 0.60, 0.60 | +0.20 | 2/2 |
| `judge-pairwise-shorter-wins` | 1.00, 1.00 | 0.33, 0.33 | +0.67 | 2/2 |
| `judge-pointwise-rubric` | 1.00, 1.00 | 0.75, 0.75 | +0.25 | 2/2 |

Scores are the weighted share of graders passed in a run (`tool_used: Skill` is an indicator, not scored, under ablation).
The one sub-1.0 with-plugin run (`extract-ticket-missing-field`) passed every deterministic grader and failed only the LLM rubric vote; the no-plugin arm failed that rubric in both runs.
Full per-run grader output is in `latest.json`; the HTML report of each run lives under the git-ignored `results/` directory.
