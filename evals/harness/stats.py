"""Small, dependency-free statistics helpers used by the reports."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


def wilson_interval(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion. Returns (low, high) in [0, 1]."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = (centre - margin) / denom
    high = (centre + margin) / denom
    return (round(max(0.0, low), 10), round(min(1.0, high), 10))


def mean_std(xs: Sequence[float]) -> tuple[float, float]:
    """Mean and sample standard deviation (n-1). Empty input returns (0, 0)."""
    n = len(xs)
    if n == 0:
        return (0.0, 0.0)
    m = sum(xs) / n
    if n == 1:
        return (m, 0.0)
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return (m, math.sqrt(var))


def percentile(xs: Sequence[float], p: float) -> float:
    """Nearest-rank percentile; p in [0, 100]. Empty input returns 0."""
    if not xs:
        return 0.0
    s = sorted(xs)
    k = max(0, min(len(s) - 1, math.ceil(p / 100.0 * len(s)) - 1))
    return float(s[k])


def cohen_kappa(a: Sequence, b: Sequence) -> float:
    """Cohen's kappa between two nominal label sequences of equal length.

    Returns 1.0 when both raters agree on every item and there is only one label
    (the usual convention), and 0.0 for empty input.
    """
    if len(a) != len(b):
        raise ValueError("label sequences must have equal length")
    n = len(a)
    if n == 0:
        return 0.0
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    labels = set(ca) | set(cb)
    expected = sum((ca[lab] / n) * (cb[lab] / n) for lab in labels)
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1 - expected)


def weighted_kappa(a: Sequence[int], b: Sequence[int], max_label: int, min_label: int = 1) -> float:
    """Quadratic-weighted kappa for ordinal labels in [min_label, max_label]."""
    if len(a) != len(b):
        raise ValueError("label sequences must have equal length")
    n = len(a)
    if n == 0:
        return 0.0
    k = max_label - min_label + 1
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        obs[x - min_label][y - min_label] += 1
    ha = [sum(row) for row in obs]
    hb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = 0.0
    den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / ((k - 1) ** 2) if k > 1 else 0.0
            exp = ha[i] * hb[j] / n
            num += w * obs[i][j]
            den += w * exp
    if den == 0:
        return 1.0
    return 1.0 - num / den
