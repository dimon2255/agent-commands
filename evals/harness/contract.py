"""Validation of the script envelope defined in evals/CONTRACT.md."""

from __future__ import annotations

from typing import Any

from .pricing import USAGE_KEYS

STATUSES = ("ok", "truncated", "refusal", "error")
REQUIRED_META = ("skill", "requested_model", "served_model", "status", "usage", "calls")


def validate_envelope(env: Any) -> list[str]:
    """Return a list of contract violations (empty when the envelope is valid)."""
    problems: list[str] = []
    if not isinstance(env, dict):
        return ["envelope is not a JSON object"]
    for key in ("ok", "output", "error", "meta"):
        if key not in env:
            problems.append(f"missing top-level key {key!r}")
    meta = env.get("meta")
    if not isinstance(meta, dict):
        problems.append("meta is not an object")
        return problems
    for key in REQUIRED_META:
        if key not in meta:
            problems.append(f"meta missing {key!r}")
    status = meta.get("status")
    if status not in STATUSES:
        problems.append(f"meta.status {status!r} not in {STATUSES}")
    if env.get("ok") is True and status != "ok":
        problems.append("ok=true but status != ok")
    if env.get("ok") is True and env.get("output") is None:
        problems.append("ok=true but output is null")
    usage = meta.get("usage")
    if not isinstance(usage, dict):
        problems.append("meta.usage is not an object")
    else:
        for key in USAGE_KEYS:
            if key in usage and not isinstance(usage[key], int):
                problems.append(f"meta.usage.{key} is not an integer")
    calls = meta.get("calls")
    if not isinstance(calls, list):
        problems.append("meta.calls is not a list")
    else:
        for i, call in enumerate(calls):
            if not isinstance(call, dict):
                problems.append(f"meta.calls[{i}] is not an object")
                continue
            for key in ("purpose", "model", "stop_reason", "usage", "latency_ms"):
                if key not in call:
                    problems.append(f"meta.calls[{i}] missing {key!r}")
    err = env.get("error")
    if err is not None and not isinstance(err, dict):
        problems.append("error must be null or an object")
    return problems
