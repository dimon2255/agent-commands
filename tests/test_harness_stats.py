import math

from evals.harness.pricing import add_usage, cost_usd, empty_usage
from evals.harness.stats import cohen_kappa, mean_std, percentile, weighted_kappa, wilson_interval


def test_wilson_interval_known_values():
    low, high = wilson_interval(0, 0)
    assert (low, high) == (0.0, 0.0)
    low, high = wilson_interval(10, 10)
    assert low > 0.69 and high == 1.0
    low, high = wilson_interval(5, 10)
    assert 0.23 < low < 0.24 and 0.76 < high < 0.77
    low, high = wilson_interval(0, 10)
    assert low == 0.0 and 0.27 < high < 0.29


def test_mean_std_and_percentile():
    assert mean_std([]) == (0.0, 0.0)
    m, sd = mean_std([2, 4, 4, 4, 5, 5, 7, 9])
    assert m == 5 and abs(sd - 2.138) < 0.001
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 95) == 5
    assert percentile([], 50) == 0.0


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "a"], ["a", "a", "a"]) == 1.0
    k = cohen_kappa(["a", "b", "a", "b", "a", "b"], ["a", "b", "b", "b", "a", "a"])
    assert abs(k - (4 / 6 - 0.5) / 0.5) < 1e-9
    assert cohen_kappa([], []) == 0.0


def test_weighted_kappa_perfect_and_imperfect():
    assert weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], 5) == 1.0
    k = weighted_kappa([1, 2, 3, 4, 5], [2, 3, 4, 5, 5], 5)
    assert 0 < k < 1


def test_cost_from_recorded_tokens():
    usage = {"input_tokens": 1_000_000, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    assert cost_usd("claude-opus-5-5", usage) == 4.0
    assert cost_usd("claude-opus-5-5-20260401", usage) == 4.0
    assert cost_usd("unknown-model", usage) is None
    assert cost_usd("claude-opus-5-5", None) is None
    total = add_usage(empty_usage(), {"input_tokens": 1, "output_tokens": 2})
    total = add_usage(total, {"input_tokens": 3})
    assert total["input_tokens"] == 4 and total["output_tokens"] == 2
    assert math.isclose(cost_usd("claude-haiku-5-5", {"input_tokens": 10_000_000, "output_tokens": 1_000_000}), 1.0 + 0.5)
