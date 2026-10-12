"""Shared evaluation harness.

The harness treats each skill's bundled script as the system under test, runs it as a
subprocess per (case, rep), classifies every attempt (scored / truncated / refusal /
infrastructure error), applies atomic graders, and writes a report with confidence
intervals, cost and latency. See ``evals/CONTRACT.md`` for the contract it enforces.
"""

from .graders import Grade, run_metric
from .runner import Runner, discover_suites, load_suite, smoke
from .stats import cohen_kappa, mean_std, percentile, wilson_interval

__all__ = [
    "Grade",
    "Runner",
    "cohen_kappa",
    "discover_suites",
    "load_suite",
    "mean_std",
    "percentile",
    "run_metric",
    "smoke",
    "wilson_interval",
]
