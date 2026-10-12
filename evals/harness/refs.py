"""Dotted-path references such as ``$output.data.total`` resolved against a case context."""

from __future__ import annotations

from typing import Any

_ROOTS = ("input", "output", "expected", "meta")


class RefError(KeyError):
    pass


def is_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$") and value[1:].split(".")[0] in _ROOTS


def resolve(value: Any, ctx: dict[str, Any]) -> Any:
    """Resolve ``$root.a.b`` against ctx; return non-reference values unchanged.

    List indices are written as path segments (``$output.items.0.name``).
    Raises RefError when the path does not exist, so a typo in a config fails loudly
    instead of silently grading against ``None``.
    """
    if not is_ref(value):
        return value
    parts = value[1:].split(".")
    cur: Any = ctx
    walked = "$"
    for part in parts:
        if isinstance(cur, dict):
            if part not in cur:
                raise RefError(f"{walked} has no key {part!r}")
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError) as exc:
                raise RefError(f"{walked} has no index {part!r}") from exc
        else:
            raise RefError(f"{walked} is a {type(cur).__name__}, cannot descend into {part!r}")
        walked += "." + part
    return cur
