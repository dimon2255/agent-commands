# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic>=1.13,<2", "pyyaml>=6.0"]
# ///
"""Rubric-based LLM-as-judge with the bias controls an eval needs before its numbers mean anything.

Modes, chosen by ``input["mode"]``:

- ``pointwise``: grade one candidate against named criteria (one model call).
- ``pairwise``: compare two candidates, judged twice with the order swapped (two calls).
- ``calibrate``: run pointwise over human-labelled items and report agreement and kappa. Run
  it before trusting the judge on a new rubric: a judge nobody has checked is an opinion.

The system prompts live in ``../prompts/*.md`` so they are reviewed and versioned as text;
their hash is recorded in ``meta.prompt_sha256`` so every result names the prompt behind it.

Machine path (evals/CONTRACT.md): ``judge.py --input case.json --json [--model] [--effort]``.
Human path: ``judge.py --mode pointwise --rubric rubric.yaml --task "..." --candidate @answer.txt``.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

SKILL = "judge"
VERSION = "0.1.0"
DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000  # thinking is always on for this model and counts against max_tokens
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
MODES = ("pointwise", "pairwise", "calibrate")
PASS_RULES = ("all", "majority")
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_S, _B = {"type": "string"}, {"type": "boolean"}
# Field order is the reasoning order: evidence before verdict, per-criterion verdicts before the overall one.
POINTWISE_SCHEMA = _obj({
    "criteria_results": {"type": "array", "items": _obj({"id": {"type": "integer"}, "evidence": _S, "reasoning": _S, "met": _B})},
    "rationale": _S, "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]}, "passed": _B,
})
PAIRWISE_SCHEMA = _obj({
    "criteria": {"type": "array", "items": _obj({"id": {"type": "integer"}, "first_evidence": _S, "first_met": _B,
                                                  "second_evidence": _S, "second_met": _B})},
    "rationale": _S, "winner": {"type": "string", "enum": ["first", "second", "tie"]},
})


@functools.cache
def prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def resolve_api_key() -> str:
    key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set CLAUDE_API_KEY (or ANTHROPIC_API_KEY).")
    return key


class Tracker:
    """Records every model call for the envelope. Locked because calibrate grades in threads."""

    def __init__(self, requested_model: str):
        self.requested_model = requested_model
        self.served_model: str | None = None
        self.status = "ok"
        self.stop_reason: str | None = None
        self.calls: list[dict[str, Any]] = []
        self.error: dict[str, Any] | None = None
        self.prompts: set[str] = set()
        self._lock = threading.Lock()

    def record(self, purpose: str, resp: Any, latency_ms: int) -> None:
        usage = {k: int(getattr(resp.usage, k, 0) or 0) for k in USAGE_KEYS}
        with self._lock:
            self.calls.append({"purpose": purpose, "model": resp.model, "stop_reason": resp.stop_reason, "usage": usage,
                               "latency_ms": latency_ms, "request_id": getattr(resp, "_request_id", None)})
            self.served_model = self.served_model or resp.model
            self.stop_reason = resp.stop_reason
            if resp.stop_reason == "max_tokens" and self.status == "ok":
                self.status = "truncated"
            if resp.stop_reason == "refusal":
                details = getattr(resp, "stop_details", None)
                self.status = "refusal"
                self.error = {"type": "refusal", "category": getattr(details, "category", None),
                              "message": getattr(details, "explanation", None) or "model refused"}

    def fail(self, exc: BaseException) -> None:
        self.status = "error"
        self.error = {"type": type(exc).__name__, "message": str(exc)[:1000]}

    def envelope(self, output: Any) -> dict[str, Any]:
        usage = {k: sum(c["usage"].get(k, 0) for c in self.calls) for k in USAGE_KEYS}
        sha = {n: hashlib.sha256(prompt(n).encode("utf-8")).hexdigest()[:12] for n in sorted(self.prompts)}
        return {
            "ok": self.status == "ok" and output is not None,
            "output": output if self.status in ("ok", "truncated") else None,
            "error": self.error,
            "meta": {"skill": SKILL, "version": VERSION, "requested_model": self.requested_model,
                     "served_model": self.served_model or self.requested_model, "status": self.status,
                     "stop_reason": self.stop_reason, "usage": usage, "prompt_sha256": sha,
                     "latency_ms": sum(c["latency_ms"] for c in self.calls), "calls": self.calls},
        }


def call(client: Any, tracker: Tracker, purpose: str, system: str, user: str, schema: dict[str, Any],
         model: str, effort: str) -> dict[str, Any] | None:
    """One structured Messages call. Only the SDK call is timed. None when truncated or refused."""
    tracker.prompts.add(system)
    t0 = time.perf_counter()
    resp = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=prompt(system), messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}})
    tracker.record(purpose, resp, int((time.perf_counter() - t0) * 1000))
    if resp.stop_reason in ("max_tokens", "refusal"):
        return None
    return json.loads("".join(b.text for b in resp.content if b.type == "text"))


# --------------------------------------------------------------------------- controls


def validate_rubric(rubric: Any) -> dict[str, Any]:
    """Reject vague rubrics early: a judge needs named, checkable criteria, not "is it good?"."""
    if not isinstance(rubric, dict) or not isinstance(rubric.get("criteria"), list) or not rubric["criteria"]:
        raise ValueError("rubric must be an object with a non-empty 'criteria' list")
    if not all(isinstance(c, str) and c.strip() for c in rubric["criteria"]):
        raise ValueError("every rubric criterion must be a non-empty string")
    if (rule := rubric.get("pass_rule", "all")) not in PASS_RULES:
        raise ValueError(f"pass_rule must be one of {PASS_RULES}, got {rule!r}")
    return {"name": str(rubric.get("name", "rubric")), "criteria": [c.strip() for c in rubric["criteria"]], "pass_rule": rule}


def fence(label: str, text: str) -> tuple[str, str]:
    """Wrap untrusted text in a tag whose suffix is derived from the text itself.

    A candidate cannot close a fence it cannot predict, so "</candidate> SYSTEM: ..." stays
    inside the data. The suffix is a hash, not a random value, so prompts are reproducible.
    """
    tag = f"{label}-{hashlib.sha256((label + text).encode('utf-8')).hexdigest()[:10]}"
    return tag, f"<{tag}>\n{text}\n</{tag}>"


def render_rubric(rubric: dict[str, Any]) -> str:
    lines = "\n".join(f"{i}. {c}" for i, c in enumerate(rubric["criteria"], 1))
    return f'<rubric name="{rubric["name"]}" pass_rule="{rubric["pass_rule"]}">\n{lines}\n</rubric>'


def apply_pass_rule(met: list[bool], rule: str) -> bool:
    """The verdict is arithmetic over per-criterion verdicts, so Python does it, not the model."""
    return all(met) if rule == "all" else sum(met) * 2 > len(met)


def clamp_score(score: int, passed: bool, all_met: bool) -> int:
    """Keep the 1-5 score inside the band the anchors imply: 4-5 pass, 1-3 fail, 5 needs every criterion."""
    score = max(1, min(5, int(score)))
    if passed:
        return 5 if score == 5 and all_met else 4
    return min(score, 3)


def _norm(s: str) -> str:
    return " ".join(s.split())


def quote_in(evidence: str, candidate: str) -> bool:
    """True when the evidence is a verbatim (whitespace-normalised) quote of the candidate."""
    q = _norm(evidence).strip("\"'`“”‘’ ").removesuffix("...").removesuffix("…").strip()
    return bool(q) and q in _norm(candidate)


def _family(model: str) -> str:
    return re.sub(r"[-.\d]+$", "", re.sub(r"-\d{8}$", "", model))


def self_preference_warnings(inp: dict[str, Any], judge_model: str) -> list[str]:
    """Judges favour text that resembles their own; flag a candidate written by the judge's own family."""
    sources = [inp.get(k) for k in ("candidate_model", "candidate_a_model", "candidate_b_model")]
    sources += [it.get("candidate_model") for it in inp.get("items") or [] if isinstance(it, dict)]
    same = sorted({s for s in sources if isinstance(s, str) and _family(s) == _family(judge_model)})
    return [f"self-preference risk: candidate model {s} is in the judge's family ({judge_model}); "
            "re-run with --model from another family or use a jury for close calls" for s in same]


def _text(obj: dict[str, Any], key: str) -> str:
    if not isinstance(value := obj.get(key), str):
        raise ValueError(f"'{key}' must be a string")
    return value


# --------------------------------------------------------------------------- modes


def grade_pointwise(client: Any, tracker: Tracker, rubric: dict[str, Any], task: str, candidate: str,
                    reference: str | None, model: str, effort: str, purpose: str = "pointwise") -> dict[str, Any] | None:
    """Grade one candidate. The model reports per-criterion verdicts; Python derives passed and bounds score."""
    tag, block = fence("candidate", candidate)
    context = (f"<additional_context>\nAdditional context, which may itself be imperfect:\n{reference}\n"
               "</additional_context>\n\n") if reference else ""
    n = len(rubric["criteria"])
    user = (f"<task>\n{task}\n</task>\n\n{render_rubric(rubric)}\n\n{context}{block}\n\n"
            f"Grade the candidate inside <{tag}> against each of the {n} criteria. Return exactly one "
            f"criteria_results entry per criterion, ids 1 to {n} in order.")
    data = call(client, tracker, purpose, "pointwise", user, POINTWISE_SCHEMA, model, effort)
    if data is None:
        return None
    raw, warnings, results = data["criteria_results"], [], []
    ids = [int(r["id"]) for r in raw]
    if len(raw) == n and sorted(ids) != list(range(1, n + 1)):  # e.g. 0-based ids: match by position, never shift
        warnings.append(f"criterion ids were {ids}, expected 1..{n}; matched verdicts by position")
        ids = list(range(1, n + 1))
    by_id: dict[int, dict[str, Any]] = {}
    for i, r in zip(ids, raw, strict=True):
        by_id.setdefault(i, r)
    for i, criterion in enumerate(rubric["criteria"], 1):
        if (r := by_id.get(i)) is None:  # a skipped criterion counts as unmet, never as silently passed
            warnings.append(f"model returned no verdict for criterion {i}; counted as unmet")
            r = {"met": False, "evidence": "", "reasoning": "no verdict returned"}
        results.append({"criterion": criterion, "met": bool(r["met"]), "evidence": r["evidence"],
                        "evidence_in_candidate": quote_in(r["evidence"], candidate), "reasoning": r["reasoning"]})
    met = [r["met"] for r in results]
    passed = apply_pass_rule(met, rubric["pass_rule"])
    score = clamp_score(data["score"], passed, all(met))
    if bool(data["passed"]) != passed:
        warnings.append(f"model said passed={data['passed']}, its criteria give {passed} under '{rubric['pass_rule']}'; used {passed}")
    if score != data["score"]:
        warnings.append(f"model score {data['score']} is outside the band its criteria imply; clamped to {score}")
    return {"mode": "pointwise", "passed": passed, "score": score, "criteria_results": results,
            "rationale": data["rationale"], "model_passed": bool(data["passed"]), "model_score": data["score"],
            "warnings": warnings}


def map_vote(order: str, positional_winner: str) -> str:
    """Translate "first"/"second" back to A/B for the order the candidates were shown in."""
    return {"first": order[0], "second": order[1]}.get(positional_winner, "tie")


def combine_votes(votes: list[dict[str, Any]]) -> tuple[str, bool]:
    """A winner must survive the swap; a verdict that flips with position is reported as a tie."""
    winners = {v["winner"] for v in votes}
    return (winners.pop(), True) if len(winners) == 1 else ("tie", False)


def compare_once(client: Any, tracker: Tracker, rubric: dict[str, Any], task: str, first: str, second: str,
                 order: str, model: str, effort: str) -> dict[str, Any] | None:
    """One ordering. Labels are positional ("first"/"second"), never A/B, so no label can carry a preference."""
    tag1, block1 = fence("first", first)
    tag2, block2 = fence("second", second)
    user = (f"<task>\n{task}\n</task>\n\n{render_rubric(rubric)}\n\n{block1}\n\n{block2}\n\n"
            f"Compare the candidates inside <{tag1}> and <{tag2}> on each of the {len(rubric['criteria'])} "
            'criteria, then choose the winner: "first", "second" or "tie".')
    data = call(client, tracker, f"pairwise-{order}", "pairwise", user, PAIRWISE_SCHEMA, model, effort)
    if data is None:
        return None
    criteria = [{"id": c["id"], order[0]: {"met": c["first_met"], "evidence": c["first_evidence"]},
                 order[1]: {"met": c["second_met"], "evidence": c["second_evidence"]}} for c in data["criteria"]]
    vote = {"order": order, "winner": map_vote(order, data["winner"]), "rationale": data["rationale"], "criteria": criteria}
    tally = {x: sum(c[x]["met"] for c in criteria) for x in "AB"}
    if (loser := {"A": "B", "B": "A"}.get(vote["winner"])) and tally[loser] > tally[vote["winner"]]:
        vote["warning"] = f"winner {vote['winner']} meets fewer criteria than {loser} in its own grading ({tally})"
    return vote


def run_pairwise(client: Any, tracker: Tracker, inp: dict[str, Any], model: str, effort: str) -> dict[str, Any] | None:
    """Two independent calls, A-then-B and B-then-A; neither sees the other's verdict."""
    rubric, task = validate_rubric(inp.get("rubric")), _text(inp, "task")
    a, b = _text(inp, "candidate_a"), _text(inp, "candidate_b")
    votes = []
    for order, first, second in (("AB", a, b), ("BA", b, a)):
        if (vote := compare_once(client, tracker, rubric, task, first, second, order, model, effort)) is None:
            return None
        votes.append(vote)
    winner, consistent = combine_votes(votes)
    rationale = votes[0]["rationale"] if consistent else (
        f"The orderings disagreed (AB chose {votes[0]['winner']}, BA chose {votes[1]['winner']}), so the verdict "
        f"depends on position and is reported as a tie. AB: {votes[0]['rationale']} BA: {votes[1]['rationale']}")
    return {"mode": "pairwise", "winner": winner, "position_consistent": consistent, "votes": votes,
            "rationale": rationale, "warnings": self_preference_warnings(inp, model)}


def cohen_kappa(a: list[Any], b: list[Any]) -> float:
    """Agreement corrected for chance (same maths as evals/harness/stats.py; this script is standalone)."""
    if (n := len(a)) == 0:
        return 0.0
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1 - expected)


def weighted_kappa(a: list[int], b: list[int], lo: int = 1, hi: int = 5) -> float:
    """Quadratic-weighted kappa: a 4-vs-5 disagreement costs far less than a 1-vs-5 one."""
    if (n := len(a)) == 0:
        return 0.0
    k = hi - lo + 1
    ha, hb = Counter(x - lo for x in a), Counter(y - lo for y in b)
    obs = Counter((x - lo, y - lo) for x, y in zip(a, b, strict=True))
    cells = [(i, j, (i - j) ** 2 / (k - 1) ** 2) for i in range(k) for j in range(k)]
    num = sum(w * obs[(i, j)] for i, j, w in cells)
    den = sum(w * ha[i] * hb[j] / n for i, j, w in cells)
    return 1.0 if den == 0 else 1.0 - num / den


def calibration_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Agreement alone flatters a judge on skewed data; kappa and the majority baseline expose that."""
    n = len(rows)
    pairs = [(r["judge_passed"], r["human_passed"]) for r in rows]
    scored = [r for r in rows if r.get("human_score") is not None]
    wk = weighted_kappa([r["judge_score"] for r in scored], [int(r["human_score"]) for r in scored]) if scored else None
    return {
        "n": n,
        "agreement": round(sum(j == h for j, h in pairs) / n, 4) if n else 0.0,
        "cohen_kappa": round(cohen_kappa([j for j, _ in pairs], [h for _, h in pairs]), 4),
        "weighted_kappa": None if wk is None else round(wk, 4),
        "confusion": {"tp": sum(j and h for j, h in pairs), "fp": sum(j and not h for j, h in pairs),
                      "tn": sum(not j and not h for j, h in pairs), "fn": sum(h and not j for j, h in pairs)},
        "majority_class_baseline": round(max(Counter(h for _, h in pairs).values()) / n, 4) if n else 0.0,
    }


def run_calibrate(client: Any, tracker: Tracker, inp: dict[str, Any], model: str, effort: str,
                  workers: int = 4) -> dict[str, Any]:
    """Grade every item blind to its human label, then compare.

    An item cut off by max_tokens is listed in ``excluded``, never guessed (envelope status
    ``truncated``). A refusal or API error on any item fails the whole run, as the envelope
    contract requires, so a partial calibration is never reported as complete.
    """
    rubric, items = validate_rubric(inp.get("rubric")), inp.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("calibrate needs a non-empty 'items' list")
    for it in items:
        if not isinstance(it, dict) or "id" not in it or not isinstance(it.get("human_passed"), bool):
            raise ValueError(f"every item needs 'id' and a boolean 'human_passed': {str(it)[:120]}")

    def one(it: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        return it, grade_pointwise(client, tracker, rubric, _text(it, "task"), _text(it, "candidate"),
                                   it.get("reference"), model, effort, purpose=f"calibrate:{it['id']}")

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(items)))) as pool:
        results = list(pool.map(one, items))
    rows = [{"id": it["id"], "judge_passed": out["passed"], "human_passed": it["human_passed"],
             "judge_score": out["score"], "human_score": it.get("human_score")} for it, out in results if out]
    return {"mode": "calibrate", **calibration_stats(rows), "items": rows,
            "excluded": [it["id"] for it, out in results if out is None],
            "warnings": self_preference_warnings(inp, model)}


def run(client: Any, tracker: Tracker, inp: dict[str, Any], model: str, effort: str, workers: int = 4) -> dict[str, Any] | None:
    mode = inp.get("mode")
    if mode == "pointwise":
        out = grade_pointwise(client, tracker, validate_rubric(inp.get("rubric")), _text(inp, "task"),
                              _text(inp, "candidate"), inp.get("reference"), model, effort)
        if out is not None:
            out["warnings"] += self_preference_warnings(inp, model)
        return out
    if mode == "pairwise":
        return run_pairwise(client, tracker, inp, model, effort)
    if mode == "calibrate":
        return run_calibrate(client, tracker, inp, model, effort, workers)
    raise ValueError(f"input.mode must be one of {MODES}, got {mode!r}")


# --------------------------------------------------------------------------- CLI


def _arg_text(value: str | None) -> str | None:
    """CLI text values may be @path to read from a file."""
    return Path(value[1:]).read_text(encoding="utf-8") if value and value.startswith("@") else value


def input_from_flags(args: argparse.Namespace) -> dict[str, Any]:
    raw = Path(args.rubric).read_text(encoding="utf-8")
    if args.rubric.endswith((".yaml", ".yml")):
        import yaml

        rubric = yaml.safe_load(raw)
    else:
        rubric = json.loads(raw)
    inp: dict[str, Any] = {"mode": args.mode, "rubric": rubric.get("rubric", rubric) if isinstance(rubric, dict) else rubric}
    if args.mode == "calibrate":
        inp["items"] = [json.loads(x) for x in Path(args.items).read_text(encoding="utf-8").splitlines() if x.strip()]
    elif args.mode == "pointwise":
        inp.update(task=_arg_text(args.task), candidate=_arg_text(args.candidate), reference=_arg_text(args.reference))
    else:
        inp.update(task=_arg_text(args.task), candidate_a=_arg_text(args.candidate_a), candidate_b=_arg_text(args.candidate_b))
    return inp


def human_summary(env: dict[str, Any]) -> str:
    out, meta = env["output"], env["meta"]
    if out is None:
        return f"judge: status={meta['status']} error={env['error']}"
    lines: list[str] = []
    if out["mode"] == "pointwise":
        met = sum(r["met"] for r in out["criteria_results"])
        lines.append(f"{'PASS' if out['passed'] else 'FAIL'}  score {out['score']}/5  ({met}/{len(out['criteria_results'])} criteria met)")
        lines += [f"  [{'x' if r['met'] else ' '}] {r['criterion']}\n        \"{r['evidence']}\"" for r in out["criteria_results"]]
    elif out["mode"] == "pairwise":
        lines.append(f"winner: {out['winner']}  (position-consistent: {'yes' if out['position_consistent'] else 'NO'})")
        lines += [f"  order {v['order']}: {v['winner']}" for v in out["votes"]]
    else:
        lines.append(f"n={out['n']}  agreement={out['agreement']}  majority baseline={out['majority_class_baseline']}  "
                     f"kappa={out['cohen_kappa']}  weighted kappa={out['weighted_kappa']}  {out['confusion']}")
        lines += [f"  disagree on {r['id']}: judge {r['judge_passed']}, human {r['human_passed']}"
                  for r in out["items"] if r["judge_passed"] != r["human_passed"]]
    if out.get("rationale"):
        lines.append(f"rationale: {out['rationale']}")
    lines += [f"warning: {w}" for w in out.get("warnings", [])]
    u = meta["usage"]
    lines.append(f"[{meta['status']}] {len(meta['calls'])} call(s), {u['input_tokens']} in / {u['output_tokens']} out tokens, "
                 f"{meta['latency_ms']} ms, model {meta['served_model']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None, client: Any = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", help="JSON file holding the input object (machine path)")
    p.add_argument("--json", action="store_true", help="print only the envelope JSON")
    p.add_argument("--model", default=DEFAULT_MODEL, help="judge model; prefer a different family from the candidates'")
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--out", help="also write the envelope JSON here")
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--rubric", help="rubric file, YAML or JSON")
    for flag in ("--task", "--candidate", "--candidate-a", "--candidate-b"):
        p.add_argument(flag, help="text, or @path to read it from a file")
    p.add_argument("--reference", help="additional context; the judge treats it as possibly imperfect")
    p.add_argument("--items", help="calibrate: JSONL of {id, task, candidate, human_passed, human_score?}")
    p.add_argument("--workers", type=int, default=4, help="calibrate: parallel calls")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.input:
        inp = json.loads(Path(args.input).read_text(encoding="utf-8"))
    elif args.mode and args.rubric:
        need = {"pointwise": ("task", "candidate"), "pairwise": ("task", "candidate_a", "candidate_b"),
                "calibrate": ("items",)}[args.mode]
        if missing := [f"--{k.replace('_', '-')}" for k in need if getattr(args, k) is None]:
            p.error(f"--mode {args.mode} needs {' '.join(missing)}")
        inp = input_from_flags(args)
    else:
        p.error("pass --input <file>, or --mode with --rubric and the mode's text flags")
    tracker = Tracker(args.model)
    output = None
    try:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=resolve_api_key(), max_retries=4)
        output = run(client, tracker, inp, args.model, args.effort, args.workers)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a typed envelope error
        tracker.fail(exc)
    env = tracker.envelope(output)
    payload = json.dumps(env, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload if args.json else human_summary(env))
    return 0


if __name__ == "__main__":
    sys.exit(main())
