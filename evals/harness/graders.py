"""Atomic graders. Each returns a Grade(score 0..1, passed, evidence).

Built-ins cover the deterministic checks every skill needs; a skill can add a
``graders_module`` with Python functions for anything domain-specific. The ``llm_rubric``
grader is the only one that spends money, and it records its usage on the Grade so the
report can keep judge cost separate from skill cost.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .refs import resolve


@dataclass
class Grade:
    score: float
    passed: bool
    evidence: str
    na: bool = False  # metric does not apply to this case (e.g. pairwise metric on a pointwise case)
    error: bool = False  # the grader itself failed (judge outage, exception); never a model failure
    judge_usage: dict | None = None
    judge_model: str | None = None
    judge_latency_ms: int | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def not_applicable(cls, evidence: str = "not applicable") -> Grade:
        return cls(0.0, False, evidence, na=True)

    @classmethod
    def grader_error(cls, evidence: str, **extra: Any) -> Grade:
        return cls(0.0, False, evidence, error=True, **extra)


@dataclass
class GradeContext:
    case: dict
    output: Any
    meta: dict
    judge: Any = None  # harness.llm.Judge or None
    custom_module: Any = None
    ref_ctx: dict = field(init=False)

    def __post_init__(self) -> None:
        self.ref_ctx = {
            "input": self.case.get("input", {}),
            "expected": self.case.get("expected", {}),
            "output": self.output,
            "meta": self.meta,
        }

    def arg(self, metric: dict, name: str, default: Any = None) -> Any:
        if name not in metric:
            return default
        return resolve(metric[name], self.ref_ctx)


_WS = re.compile(r"\s+")


def normalize(value: Any) -> str:
    """Normalise a scalar for lenient comparison: trim, casefold, collapse whitespace, 4 == 4.0."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        f = float(value)
        return str(int(f)) if f.is_integer() else repr(f)
    s = _WS.sub(" ", str(value)).strip().casefold()
    # numeric strings: "1,234.00" -> "1234"
    compact = s.replace(",", "").replace("$", "").strip()
    try:
        f = float(compact)
        return str(int(f)) if f.is_integer() else repr(f)
    except ValueError:
        return s


def _g_exact(metric: dict, ctx: GradeContext) -> Grade:
    target = ctx.arg(metric, "target")
    expected = ctx.arg(metric, "expected")
    ok = normalize(target) == normalize(expected)
    return Grade(1.0 if ok else 0.0, ok, f"got {target!r}, expected {expected!r}")


def _g_contains(metric: dict, ctx: GradeContext) -> Grade:
    target = normalize(ctx.arg(metric, "target"))
    needle = normalize(ctx.arg(metric, "needle"))
    ok = bool(needle) and needle in target
    return Grade(1.0 if ok else 0.0, ok, f"needle {needle!r} {'found' if ok else 'not found'}")


def _g_regex(metric: dict, ctx: GradeContext) -> Grade:
    target = ctx.arg(metric, "target")
    pattern = ctx.arg(metric, "pattern")
    flags = 0
    for ch in str(ctx.arg(metric, "flags", "") or ""):
        flags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}.get(ch, 0)
    text = target if isinstance(target, str) else ("" if target is None else str(target))
    m = re.search(pattern, text, flags)
    ok = m is not None
    if ctx.arg(metric, "match", "contains") == "not_contains":
        ok = not ok
    return Grade(1.0 if ok else 0.0, ok, f"pattern {pattern!r} {'matched' if m else 'did not match'}")


def _g_json_schema(metric: dict, ctx: GradeContext) -> Grade:
    import jsonschema

    target = ctx.arg(metric, "target")
    schema = ctx.arg(metric, "schema")
    # FormatChecker so `format: date` / `email` are enforced, not silently ignored.
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(target), key=lambda e: list(e.path))
    if not errors:
        return Grade(1.0, True, "valid against schema")
    first = errors[0]
    where = "/".join(str(p) for p in first.path) or "<root>"
    return Grade(0.0, False, f"{len(errors)} schema error(s); first at {where}: {first.message[:160]}")


def _g_paths_subset(metric: dict, ctx: GradeContext) -> Grade:
    target = ctx.arg(metric, "target") or []
    allowed = set(ctx.arg(metric, "allowed") or [])
    if not isinstance(target, list):
        return Grade(0.0, False, f"target is {type(target).__name__}, expected list")
    norm = lambda p: re.sub(r"^(\./)+", "", str(p).replace("\\", "/"))  # noqa: E731 - strip leading ./ only
    allowed_n = {norm(p) for p in allowed}
    bad = [p for p in target if norm(p) not in allowed_n]
    if not target:
        return Grade(1.0, True, "no paths referenced")
    score = 1.0 - len(bad) / len(target)
    return Grade(score, not bad, f"{len(bad)}/{len(target)} referenced paths not in context: {bad[:5]}")


def _g_llm_rubric(metric: dict, ctx: GradeContext) -> Grade:
    if ctx.judge is None:
        # No judge configured (--no-judge, or a smoke run): the metric is not evaluated,
        # which is different from the candidate failing it.
        return Grade.not_applicable("no judge configured")
    rubric = ctx.arg(metric, "rubric")
    target = ctx.arg(metric, "target")
    context = ctx.arg(metric, "context", "") or ""
    candidate = target if isinstance(target, str) else _dump(target)
    from .llm import JudgeError

    try:
        res = ctx.judge.grade(str(rubric), candidate, str(context))
    except JudgeError as exc:
        # The judge refused or was cut off: a grader failure with its own cost, not a model failure.
        return Grade.grader_error(
            f"JUDGE ERROR {exc}", judge_usage=exc.usage, judge_model=exc.served_model, judge_latency_ms=exc.latency_ms
        )
    return Grade(
        score=(res.score - 1) / 4.0,
        passed=res.passed,
        evidence=f"judge score {res.score}/5: {res.rationale}",
        judge_usage=res.usage,
        judge_model=res.served_model,
        judge_latency_ms=res.latency_ms,
    )


def _g_python(metric: dict, ctx: GradeContext) -> Grade:
    if ctx.custom_module is None:
        raise RuntimeError("python grader needs graders_module in config.yaml")
    fn = getattr(ctx.custom_module, metric["function"], None)
    if fn is None:
        raise RuntimeError(f"graders_module has no function {metric['function']!r}")
    result = fn(ctx.case, ctx.output, ctx.meta)
    if isinstance(result, Grade):
        return result
    if isinstance(result, dict):
        if result.get("na"):
            return Grade.not_applicable(str(result.get("evidence", "not applicable")))
        return Grade(float(result["score"]), bool(result["passed"]), str(result.get("evidence", "")))
    raise TypeError(f"{metric['function']} returned {type(result).__name__}, expected dict or Grade")


def _dump(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


BUILTIN = {
    "exact": _g_exact,
    "contains": _g_contains,
    "regex": _g_regex,
    "json_schema": _g_json_schema,
    "paths_subset": _g_paths_subset,
    "llm_rubric": _g_llm_rubric,
    "python": _g_python,
}


def load_custom_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"graders_{path.stem}_{abs(hash(str(path)))}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load graders module {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_metric(metric: dict, ctx: GradeContext) -> Grade:
    """Run one metric; grader exceptions are converted into a failed Grade with evidence.

    A grader that crashes must never silently count as a pass, and a crash on one metric
    must not take the other metrics of the same case down with it.
    """
    kind = metric.get("grader")
    fn = BUILTIN.get(kind)
    if fn is None:
        raise RuntimeError(f"unknown grader {kind!r} in metric {metric.get('name')!r}")
    try:
        return fn(metric, ctx)
    except Exception as exc:  # noqa: BLE001 - grader failures are reported, not raised
        # A grader that crashes is excluded from the pass rate and fails the gate as an
        # infrastructure problem; it must never be averaged in as a model failure.
        return Grade.grader_error(f"GRADER ERROR {type(exc).__name__}: {str(exc)[:200]}")
