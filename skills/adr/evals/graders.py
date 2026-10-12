"""Custom graders for the adr suite.

Each function is one atomic property: ``fn(case, output, meta) -> {"score", "passed",
"evidence"}`` or ``{"na": True, "evidence"}`` when the property does not apply to the case.

The path check here is written independently of ``scripts/adr.py`` on purpose. A grader
that imported the code under test would share its blind spots; this one tokenises
differently and follows the same documented rules, and ``tests/test_adr.py`` runs the same
inputs through both. It scans the markdown only and ignores the model's own
``referenced_paths`` and the script's ``path_check``, so neither can vouch for itself.
"""

from __future__ import annotations

import re
from typing import Any

CODE_EXTENSIONS = ("py", "pyi", "ts", "tsx", "js", "jsx", "mjs", "cjs", "cs", "java", "kt", "go", "rs",
                   "rb", "md", "yaml", "yml", "json", "toml", "sql", "sh", "ps1", "cfg", "ini", "env",
                   "tf", "tfvars", "hcl", "proto", "txt", "lock", "xml", "csproj", "conf", "mts", "cts")
_EXT = re.compile(r"\.(?:" + "|".join(CODE_EXTENSIONS) + r")$")  # case-sensitive: threading.Lock is code
_PRODUCT = re.compile(r"^[A-Za-z]+\.js$")  # Node.js, Next.js
_IDIOMS = {"process.env", "import.meta.env"}
_PATH_CHARS = re.compile(r"[\w./\\-]+")
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+\S", re.M)
_H3 = re.compile(r"^###\s+\S", re.M)
HEADERS = {
    "title": r"^#\s+ADR\s+\d+\s*[:.\-\u2013\u2014]\s*\S",
    "Context": r"^##\s+Context\s*$",
    "Decision": r"^##\s+Decision\s*$",
    "Alternatives considered": r"^##\s+Alternatives considered\s*$",
    "Consequences": r"^##\s+Consequences\s*$",
}


def _md(output: Any) -> str:
    md = output.get("markdown") if isinstance(output, dict) else None
    return md if isinstance(md, str) else ""


def _norm(path: str) -> str:
    p = re.sub(r"/+", "/", str(path).strip().replace("\\", "/"))
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _loose(text: str) -> str:
    """Casefold, drop Markdown emphasis and code marks, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", str(text))).strip().casefold()


def _section(markdown: str, title: str) -> str | None:
    lines = markdown.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(HEADERS[title], ln, re.I)), None)
    if start is None:
        return None
    end = next((j for j in range(start + 1, len(lines)) if re.match(r"#{1,2}\s", lines[j])), len(lines))
    return "\n".join(lines[start + 1: end])


def classify_markdown_paths(markdown: str, allowed: list[str]) -> tuple[list[str], list[str]]:
    """Return (grounded, unknown) path tokens found in the markdown.

    Rules (shared with the script, implemented separately): a token is a path claim when it
    ends in a code-ish extension or contains a separator. It is grounded when it equals an
    allowed path or an ancestor directory of one, or is a suffix of either aligned on a
    segment (``session.py`` for ``src/session.py``). An ungrounded token counts as unknown
    when it has an extension (bare ``Node.js``-style product names excepted) or uses
    directory notation (``src/workers/``). Not claims: prose with a slash (``read/write``),
    leading-slash tokens (URL routes, absolute paths), tokens right after ``:`` or ``@``
    (URLs, host:port, package scopes), tokens glued to template syntax (``invoices/{id}.pdf``,
    ``<dir>/``, ``${VAR}``), glob suffixes (``*.md``), calls (``res.json(...)``) and the
    idioms ``process.env`` and ``import.meta.env``.
    """
    files = {_norm(p) for p in allowed}
    dirs = {"/".join(f.split("/")[:i]) for f in files for i in range(1, len(f.split("/")))}
    known = files | dirs
    grounded: list[str] = []
    unknown: list[str] = []
    for m in _PATH_CHARS.finditer(markdown):
        prev = markdown[m.start() - 1] if m.start() else " "
        nxt = markdown[m.end()] if m.end() < len(markdown) else " "
        raw = m.group(0).rstrip(".")
        if prev in "{}<>$:@" or nxt in "{}<>$(" or (prev == "*" and raw.startswith(".")) or raw in _IDIOMS:
            continue
        if not raw or raw[0] in "/\\":
            continue
        tok = _norm(raw)
        has_sep = "/" in tok or raw[-1] in "/\\"
        has_ext = bool(_EXT.search(tok))
        if not tok or not (has_sep or has_ext):
            continue
        if has_ext and not re.search(r"[\w-]", tok.rsplit(".", 1)[0]):
            continue  # a bare extension in prose ("the `.js` module mapper") is not a path claim
        if tok in known or any(k.endswith("/" + tok) for k in known):
            target = grounded
        elif (has_ext and not ("/" not in tok and _PRODUCT.match(tok))) or raw[-1] in "/\\":
            target = unknown
        else:
            continue
        if tok not in target:
            target.append(tok)
    return grounded, unknown


def sections_present(case: dict, output: Any, meta: dict) -> dict:
    md = _md(output)
    missing = [name for name, pat in HEADERS.items() if not re.search(pat, md, re.M | re.I)]
    score = 1 - len(missing) / len(HEADERS)
    found = "all five headers present" if not missing else f"missing: {', '.join(missing)}"
    return {"score": score, "passed": not missing, "evidence": f"{found}; words={len(md.split())}"}


def two_plus_alternatives(case: dict, output: Any, meta: dict) -> dict:
    alts = output.get("alternatives") if isinstance(output, dict) else None
    n_json = sum(1 for a in alts or [] if isinstance(a, dict) and str(a.get("name", "")).strip())
    body = _section(_md(output), "Alternatives considered") or ""
    # One item per H3 subsection when the section uses them (their bullets are details),
    # otherwise one per top-level list item.
    n_md = len(_H3.findall(body)) or len(_BULLET.findall(body))
    ok = n_json >= 2 and n_md >= 2
    return {"score": 1.0 if ok else 0.0, "passed": ok,
            "evidence": f"alternatives={n_json} markdown_items={n_md}"}


def negative_consequence_present(case: dict, output: Any, meta: dict) -> dict:
    cons = output.get("consequences") if isinstance(output, dict) else None
    negs = [str(n) for n in (cons or {}).get("negative") or [] if str(n).strip()]
    if not negs:
        return {"score": 0.0, "passed": False, "evidence": "negatives=0 in output.consequences.negative"}
    body = _section(_md(output), "Consequences")
    if body is None:
        return {"score": 0.0, "passed": False, "evidence": f"negatives={len(negs)} but no Consequences section"}
    haystack = _loose(body)
    found = [n for n in negs if _loose(re.sub(r"^\s*[-*+]\s+", "", n))[:30] in haystack]
    return {"score": 1.0 if found else 0.0, "passed": bool(found),
            "evidence": f"negatives={len(negs)} found_in_markdown={len(found)}"}


def paths_grounded(case: dict, output: Any, meta: dict) -> dict:
    grounded, unknown = classify_markdown_paths(_md(output), case["expected"]["allowed_paths"])
    total = len(grounded) + len(unknown)
    if total == 0:
        return {"score": 0.0, "passed": False,
                "evidence": "paths=0 unknown=0: the record cites no file from the context pack"}
    detail = f": {', '.join(unknown[:8])}" if unknown else ""
    return {"score": len(grounded) / total, "passed": not unknown,
            "evidence": f"paths={total} unknown={len(unknown)}{detail}"}


def forbidden_path_absent(case: dict, output: Any, meta: dict) -> dict:
    forbidden = [_norm(p) for p in case["expected"].get("forbidden_paths") or []]
    if not forbidden:
        return {"na": True, "evidence": "case has no forbidden paths"}
    allowed_names = {_norm(p).rsplit("/", 1)[-1].casefold() for p in case["expected"].get("allowed_paths") or []}
    tokens = {_norm(t.rstrip(".")).casefold() for t in _PATH_CHARS.findall(_md(output))}
    hits = []
    for path in forbidden:
        name = path.rsplit("/", 1)[-1].casefold()
        # A bare file name counts only when it has an extension and no allowed file shares it;
        # otherwise a forbidden "src/services/orders" would fire on the word "orders".
        bare_ok = "." in name and name not in allowed_names
        if any(t == path.casefold() or t.endswith("/" + path.casefold())
               or (bare_ok and (t == name or t.endswith("/" + name))) for t in tokens):
            hits.append(path)
    return {"score": 0.0 if hits else 1.0, "passed": not hits,
            "evidence": f"cited forbidden: {', '.join(hits)}" if hits else f"none of {len(forbidden)} forbidden path(s) cited"}


def constraints_named(case: dict, output: Any, meta: dict) -> dict:
    """Every item must appear (case-insensitive); an item that is a list passes on any of its options."""
    items = case["expected"].get("must_mention_constraints") or []
    if not items:
        return {"na": True, "evidence": "case has no constraints to name"}
    haystack = _loose(_md(output))
    missing = [opts[0] for opts in ([i] if isinstance(i, str) else list(i) for i in items)
               if not any(_loose(o) in haystack for o in opts)]
    return {"score": 1 - len(missing) / len(items), "passed": not missing,
            "evidence": "all constraints named" if not missing else f"not named: {missing}"}


def suite_metrics(rows: list[dict]) -> dict:
    """Totals that only exist across attempts, parsed from grader evidence."""
    unknown_total, with_unknown, alt_counts, words = 0, 0, [], []
    for row in rows:
        grades = row.get("grades") or {}
        m = re.search(r"words=(\d+)", str((grades.get("sections_present") or {}).get("evidence", "")))
        if m:
            words.append(int(m.group(1)))
        m = re.search(r"unknown=(\d+)", str((grades.get("paths_grounded") or {}).get("evidence", "")))
        if m:
            unknown_total += int(m.group(1))
            with_unknown += int(m.group(1)) > 0
        m = re.search(r"alternatives=(\d+)", str((grades.get("two_plus_alternatives") or {}).get("evidence", "")))
        if m:
            alt_counts.append(int(m.group(1)))
    return {
        "unknown_paths_total": unknown_total,
        "attempts_with_unknown_paths": f"{with_unknown}/{len(rows)}",
        "mean_alternatives": round(sum(alt_counts) / len(alt_counts), 2) if alt_counts else None,
        # The prompt's 700-word limit is reported, not gated: length is a style rule, not correctness.
        "mean_words": round(sum(words) / len(words)) if words else None,
        "attempts_over_700_words": f"{sum(w > 700 for w in words)}/{len(words)}",
    }
