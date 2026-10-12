"""Custom graders for the judge skill's eval suite.

Each grader checks one property of the judge's output against the human label in
``case["expected"]``. A metric that does not apply to a case (a pairwise metric on a
pointwise case, a score metric on a case with no human score) returns ``{"na": True}`` so it
is excluded from that metric's denominator instead of counting as a pass or a fail.

``suite_metrics`` computes the statistics that only exist across cases: chance-corrected
agreement (Cohen's kappa on pass/fail, quadratic-weighted kappa on the 1-5 score), agreement
split by clear-cut, borderline and known-negative cases, the majority-class baseline that raw
agreement must beat, and the position-flip rate of pairwise verdicts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evals.harness.stats import cohen_kappa, weighted_kappa

CASES_PATH = Path(__file__).with_name("cases.jsonl")
_AGREE_EVIDENCE = re.compile(r"judge_passed=(\w+) judge_score=(\w+) human_passed=(\w+) human_score=(\w+)")
_QUOTE_CHARS = "\"'`“”‘’ "


def _na(why: str) -> dict[str, Any]:
    return {"na": True, "evidence": why}


def _grade(ok: bool, evidence: str) -> dict[str, Any]:
    return {"score": 1.0 if ok else 0.0, "passed": bool(ok), "evidence": evidence}


def _mode(case: dict) -> str | None:
    return (case.get("input") or {}).get("mode")


def _get(output: Any, key: str) -> Any:
    return output.get(key) if isinstance(output, dict) else None


def _is_verbatim(evidence: str, candidate: str) -> bool:
    """Whitespace-normalised substring test. Wrapping quote marks and a trailing ellipsis are
    tolerated because they frame a quote without changing it; anything else must match exactly."""
    q = " ".join(evidence.split()).strip(_QUOTE_CHARS).removesuffix("...").removesuffix("…").strip()
    return bool(q) and q in " ".join(candidate.split())


def agrees_with_human(case: dict, output: Any, meta: dict) -> dict[str, Any]:
    """Judge pass/fail equals the human label. The evidence string feeds suite_metrics."""
    if _mode(case) == "pairwise":
        return _na("pairwise case: no pass/fail label")
    exp = case["expected"]
    jp, js = _get(output, "passed"), _get(output, "score")
    evidence = f"judge_passed={jp} judge_score={js} human_passed={exp['human_passed']} human_score={exp.get('human_score')}"
    return _grade(isinstance(jp, bool) and jp == exp["human_passed"], evidence)


def score_within_one(case: dict, output: Any, meta: dict) -> dict[str, Any]:
    """Judge 1-5 score is within one point of the human score."""
    hs = case["expected"].get("human_score")
    if hs is None:
        return _na("no human_score for this case")
    js = _get(output, "score")
    ok = isinstance(js, int) and not isinstance(js, bool) and abs(js - hs) <= 1
    return _grade(ok, f"judge_score={js} human_score={hs}")


def picks_correct_winner(case: dict, output: Any, meta: dict) -> dict[str, Any]:
    """Pairwise winner equals the labelled winner. A position-dependent tie counts as wrong."""
    if _mode(case) != "pairwise":
        return _na("not a pairwise case")
    winner, expected = _get(output, "winner"), case["expected"]["winner"]
    return _grade(winner == expected, f"winner={winner} expected={expected}")


def position_consistent(case: dict, output: Any, meta: dict) -> dict[str, Any]:
    """Both orderings produced the same winner, checked against the votes themselves, not only the flag."""
    if _mode(case) != "pairwise":
        return _na("not a pairwise case")
    flag = _get(output, "position_consistent")
    votes = [v for v in (_get(output, "votes") or []) if isinstance(v, dict)]
    orders = sorted(v.get("order") for v in votes)
    agree = orders == ["AB", "BA"] and len({v.get("winner") for v in votes}) == 1
    detail = ", ".join(f"{v.get('order')}->{v.get('winner')}" for v in votes) or "no votes"
    return _grade(flag is True and agree, f"position_consistent={flag}; votes {detail}")


def known_negative_fails(case: dict, output: Any, meta: dict) -> dict[str, Any]:
    """Empty, "I don't know", wrong-question and injection candidates must be failed."""
    if "negative" not in (case.get("tags") or []):
        return _na("not a known negative")
    passed = _get(output, "passed")
    return _grade(passed is False, f"passed={passed}; a known negative must fail")


def criteria_have_evidence(case: dict, output: Any, meta: dict) -> dict[str, Any]:
    """Every criterion verdict carries evidence, and at least one piece is a verbatim quote."""
    if _mode(case) != "pointwise":
        return _na("not a pointwise case")
    candidate = (case.get("input") or {}).get("candidate") or ""
    if not candidate.strip():
        return _na("empty candidate: there is nothing to quote")
    results = _get(output, "criteria_results")
    if not isinstance(results, list) or not results:
        return _grade(False, "no criteria_results")
    evidence = [str(r.get("evidence") or "") if isinstance(r, dict) else "" for r in results]
    empty = sum(not e.strip() for e in evidence)
    verbatim = sum(_is_verbatim(e, candidate) for e in evidence)
    return _grade(empty == 0 and verbatim >= 1,
                  f"{len(evidence)} criteria: {empty} with empty evidence, {verbatim} verbatim quotes")


def _rate(hits: list[bool]) -> float | None:
    return round(sum(hits) / len(hits), 3) if hits else None


def suite_metrics(rows: list[dict]) -> dict[str, Any]:
    """Cross-case statistics. Human labels come from cases.jsonl; judge verdicts from grade evidence."""
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    cases = {c["id"]: c for c in (json.loads(x) for x in lines if x.strip())}
    judged: list[tuple[dict, bool, int | None]] = []
    flips: list[bool] = []
    for row in rows:
        case, grades = cases.get(row["case_id"]), row.get("grades") or {}
        if case is None:
            continue
        if _mode(case) == "pairwise":
            g = grades.get("position_consistent")
            if g and not g.get("na"):
                flips.append(not g["passed"])
            continue
        g = grades.get("agrees_with_human") or {}
        m = _AGREE_EVIDENCE.search(str(g.get("evidence", "")))
        if m and m.group(1) in ("True", "False"):  # a GRADER ERROR or missing output has no verdict to count
            judged.append((case, m.group(1) == "True", int(m.group(2)) if m.group(2).isdigit() else None))

    def agreement(keep) -> tuple[float | None, int]:
        hits = [j == c["expected"]["human_passed"] for c, j, _ in judged if keep(c)]
        return _rate(hits), len(hits)

    tags = lambda c: c.get("tags") or []  # noqa: E731
    overall, n = agreement(lambda c: True)
    clear, n_clear = agreement(lambda c: tags(c)[:1] == ["pointwise"] and "borderline" not in tags(c))
    border, n_border = agreement(lambda c: "borderline" in tags(c))
    negative, n_negative = agreement(lambda c: tags(c)[:1] == ["negative"])
    human = [c["expected"]["human_passed"] for c, _, _ in judged]
    scores = [(js, c["expected"]["human_score"]) for c, _, js in judged
              if js is not None and c["expected"].get("human_score") is not None]
    return {
        "pointwise_n": n,
        "agreement": overall,
        "agreement_clear_cut": clear, "n_clear_cut": n_clear,
        "agreement_borderline": border, "n_borderline": n_border,
        "agreement_known_negative": negative, "n_known_negative": n_negative,
        "majority_class_baseline": round(max(human.count(True), human.count(False)) / n, 3) if n else None,
        "cohen_kappa_pass_fail": round(cohen_kappa([j for _, j, _ in judged], human), 3) if n else None,
        "weighted_kappa_score_1_5": round(weighted_kappa([a for a, _ in scores], [b for _, b in scores], 5), 3) if scores else None,
        "judge_pass_rate": _rate([j for _, j, _ in judged]),
        "human_pass_rate": _rate(human),
        "pairwise_n": len(flips),
        "position_flip_rate": _rate(flips),
    }
