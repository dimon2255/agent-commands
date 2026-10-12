# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic>=1.13,<2"]
# ///
"""Reference implementation of the envelope in evals/CONTRACT.md.

Copy ``Tracker`` and ``call`` into a skill script and replace ``do_work``. Run it to see a
valid envelope:

    uv run evals/script_skeleton.py --input input.json --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

SKILL = "skeleton"
VERSION = "0.1.0"
DEFAULT_MODEL = "claude-opus-5-5"
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def resolve_api_key() -> str:
    key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set CLAUDE_API_KEY (or ANTHROPIC_API_KEY).")
    return key


class Tracker:
    """Records every model call so the envelope can report usage, status and served model."""

    def __init__(self, requested_model: str):
        self.requested_model = requested_model
        self.served_model: str | None = None
        self.status = "ok"
        self.stop_reason: str | None = None
        self.calls: list[dict[str, Any]] = []
        self.error: dict[str, Any] | None = None

    def record(self, purpose: str, resp: Any, latency_ms: int) -> None:
        usage = {k: int(getattr(resp.usage, k, 0) or 0) for k in USAGE_KEYS}
        self.calls.append(
            {
                "purpose": purpose,
                "model": resp.model,
                "stop_reason": resp.stop_reason,
                "usage": usage,
                "latency_ms": latency_ms,
                "request_id": getattr(resp, "_request_id", None),
            }
        )
        if self.served_model is None:
            self.served_model = resp.model
        self.stop_reason = resp.stop_reason
        if resp.stop_reason == "max_tokens" and self.status == "ok":
            self.status = "truncated"
        if resp.stop_reason == "refusal":
            self.status = "refusal"
            details = getattr(resp, "stop_details", None)
            self.error = {
                "type": "refusal",
                "category": getattr(details, "category", None),
                "message": getattr(details, "explanation", None) or "model refused",
            }

    def fail(self, exc: BaseException) -> None:
        self.status = "error"
        self.error = {"type": type(exc).__name__, "message": str(exc)[:1000]}

    def usage_total(self) -> dict[str, int]:
        total = {k: 0 for k in USAGE_KEYS}
        for c in self.calls:
            for k in USAGE_KEYS:
                total[k] += c["usage"].get(k, 0)
        return total

    def envelope(self, output: Any) -> dict[str, Any]:
        ok = self.status == "ok" and output is not None
        return {
            "ok": ok,
            "output": output if self.status in ("ok", "truncated") else None,
            "error": self.error,
            "meta": {
                "skill": SKILL,
                "version": VERSION,
                "requested_model": self.requested_model,
                "served_model": self.served_model or self.requested_model,
                "status": self.status,
                "stop_reason": self.stop_reason,
                "usage": self.usage_total(),
                "latency_ms": sum(c["latency_ms"] for c in self.calls),
                "calls": self.calls,
            },
        }


def call(client: Any, tracker: Tracker, purpose: str, **kwargs: Any) -> Any:
    """One Messages API call with timing + tracking. Only the SDK call is timed."""
    t0 = time.perf_counter()
    resp = client.messages.create(**kwargs)
    tracker.record(purpose, resp, int((time.perf_counter() - t0) * 1000))
    return resp


def text_of(resp: Any) -> str:
    return "".join(b.text for b in resp.content if b.type == "text")


def do_work(client: Any, tracker: Tracker, inp: dict[str, Any], model: str, effort: str) -> dict[str, Any] | None:
    """Replace with the skill's logic. Return the output object, or None if no answer."""
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    resp = call(
        client,
        tracker,
        "answer",
        model=model,
        max_tokens=8000,
        system="Answer briefly.",
        messages=[{"role": "user", "content": inp.get("question", "Say hello.")}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if resp.stop_reason == "refusal":
        return None
    return json.loads(text_of(resp))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--json", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default="medium")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    with open(args.input, encoding="utf-8") as f:
        inp = json.load(f)
    tracker = Tracker(args.model)
    output = None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=resolve_api_key(), max_retries=4)
        output = do_work(client, tracker, inp, args.model, args.effort)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a typed envelope error
        tracker.fail(exc)
    env = tracker.envelope(output)
    payload = json.dumps(env, ensure_ascii=False, indent=None if args.json else 2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
