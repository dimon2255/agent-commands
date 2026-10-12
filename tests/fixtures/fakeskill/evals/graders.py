def answer_is_short(case, output, meta):
    ans = (output or {}).get("answer") if isinstance(output, dict) else None
    ok = isinstance(ans, str) and 0 < len(ans) <= 20
    return {"score": 1.0 if ok else 0.0, "passed": ok, "evidence": f"answer={ans!r}"}
