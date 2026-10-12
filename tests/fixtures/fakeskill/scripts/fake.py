"""Fake skill entrypoint used to test the harness without the API.

The case input drives the behaviour:
  echo          -> returned as output
  force_status  -> ok | truncated | refusal | error
  served_model  -> override the served model (to test mismatch detection)
  crash         -> exit non-zero
  garbage       -> print non-JSON
"""

import argparse
import json
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--json", action="store_true")
    p.add_argument("--model", default="fake-model")
    p.add_argument("--effort", default="medium")
    args = p.parse_args()
    with open(args.input, encoding="utf-8") as f:
        inp = json.load(f)
    if inp.get("crash"):
        print("boom", file=sys.stderr)
        return 3
    if inp.get("garbage"):
        print("this is not json")
        return 0
    status = inp.get("force_status", "ok")
    output = inp.get("echo") if status in ("ok", "truncated") else None
    env = {
        "ok": status == "ok" and output is not None,
        "output": output,
        "error": None if status in ("ok", "truncated") else {"type": status, "message": "forced"},
        "meta": {
            "skill": "fakeskill",
            "version": "0.0.1",
            "requested_model": args.model,
            "served_model": inp.get("served_model", args.model),
            "status": status,
            "stop_reason": {"ok": "end_turn", "truncated": "max_tokens", "refusal": "refusal", "error": None}[status],
            "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
            "latency_ms": 12,
            "calls": [
                {
                    "purpose": "fake",
                    "model": inp.get("served_model", args.model),
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                    "latency_ms": 12,
                }
            ],
        },
    }
    print(json.dumps(env))
    return 0


if __name__ == "__main__":
    sys.exit(main())
