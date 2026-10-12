def answer_is_short(case, output, meta):
    ans = (output or {}).get("answer") if isinstance(output, dict) else None
    ok = isinstance(ans, str) and 0 < len(ans) <= 20
    return {"score": 1.0 if ok else 0.0, "passed": ok, "evidence": f"answer={ans!r}"}


def edge_only(case, output, meta):
    """Applies only to cases tagged 'edge'; everything else is not applicable."""
    if "edge" not in (case.get("tags") or []):
        return {"na": True, "evidence": "not an edge case"}
    ans = (output or {}).get("answer") if isinstance(output, dict) else None
    ok = ans is not None
    return {"score": 1.0 if ok else 0.0, "passed": ok, "evidence": f"answer={ans!r}"}


def suite_metrics(rows):
    return {"scored_rows": len(rows)}
