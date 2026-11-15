#!/usr/bin/env python3
"""comment_audit.py - count function definitions that lack a preceding comment.

Usage: python .dsh/tools/comment_audit.py src/*.c

Heuristic: a line that looks like a function signature (ends with `)` and is
followed by `{`) counts as commented when the nearest previous non-empty line
ends a block comment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FUNC = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w \t\*]*\s+\**(\w+)\s*\([^;]*\)\s*$"
)


def has_doxygen(lines: list[str], idx: int) -> bool:
    k = idx - 1
    while k >= 0 and not lines[k].strip():
        k -= 1
    if k < 0 or not lines[k].strip().endswith("*/"):
        return False
    end = k
    start = end
    while start >= 0 and not lines[start].strip().startswith("/*"):
        start -= 1
    if start < 0 or not lines[start].strip().startswith("/**"):
        return False
    block = "\n".join(lines[start:end + 1])
    return "@brief" in block


def audit(path: Path) -> list[tuple[int, str, bool]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[tuple[int, str, bool]] = []
    for i, line in enumerate(lines):
        m = FUNC.match(line)
        if not m:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or not lines[j].lstrip().startswith("{"):
            continue
        commented = has_doxygen(lines, i)
        rows.append((i + 1, m.group(1), commented))
    return rows


def main() -> int:
    files = [Path(p) for p in sys.argv[1:]]
    if not files:
        print("usage: comment_audit.py <file.c> ...")
        return 2
    total = 0
    missing = 0
    for f in files:
        rows = audit(f)
        bad = [r for r in rows if not r[2]]
        total += len(rows)
        missing += len(bad)
        print(f"{f}: {len(rows) - len(bad)}/{len(rows)} functions commented")
        for line, name, ok in bad:
            print(f"  - line {line}: {name}()")
    print(f"\nTOTAL {total - missing}/{total} commented, {missing} missing")
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
