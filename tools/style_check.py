#!/usr/bin/env python3
"""style_check.py - mechanical style gate for c-embedded-coding (L0/L1).

Usage:
  python .dsh/tools/style_check.py src/foo.c
  python .dsh/tools/style_check.py --all iomux/src iomux/include

Output starts with PASS or FAIL so pipeline_gate.py can consume it:
  PASS  src/foo.c
  FAIL  src/foo.c
    - line 12: typedef struct
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BANNED = ("strcpy", "strcat", "sprintf", "gets", "alloca")
CJK = re.compile(r"[\u4e00-\u9fff]")
STRUCT_TYPEDEF = re.compile(r"typedef\s+struct")
SWITCH = re.compile(r"\bswitch\s*\(")
DEFAULT = re.compile(r"\bdefault\s*:")
GUARD = re.compile(r"^#ifndef\s+\w+", re.M)


def check_file(path: Path, allow_printf: bool) -> list[str]:
    errs: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            errs.append(f"line {i}: >120 columns ({len(line)})")
        if line.startswith(" ") and not line.lstrip().startswith(("*", "*/", "/*")):
            errs.append(f"line {i}: space indent (use tabs)")
        if CJK.search(line):
            errs.append(f"line {i}: non-English comment/text")

    if path.suffix in (".c", ".h") and STRUCT_TYPEDEF.search(text):
        errs.append("typedef struct detected (use struct tags)")
        if path.suffix == ".h" and not GUARD.search(text):
            errs.append("header without include guard")

    for name in BANNED:
        if re.search(rf"\b{name}\s*\(", text):
            errs.append(f"banned function: {name}()")

    if not allow_printf and re.search(r"(?<![\w.])(printf|fprintf)\s*\(", text):
        errs.append("bare printf/fprintf (use the project log wrapper)")

    for m in SWITCH.finditer(text):
        tail = text[m.end():m.end() + 1200]
        if not DEFAULT.search(tail):
            line = text[:m.start()].count("\n") + 1
            errs.append(f"line {line}: switch without default")

    if path.suffix == ".h" and "include" in path.parts:
        if not re.search(r"@param|@return", text):
            errs.append("public header without Doxygen @param/@return")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", nargs="*", default=None, help="directories to scan")
    ap.add_argument("--allow-printf", action="store_true")
    args = ap.parse_args()

    files: list[Path] = [Path(p) for p in args.paths]
    for d in args.all or []:
        root = Path(d)
        files.extend(sorted(root.rglob("*.c")))
        files.extend(sorted(root.rglob("*.h")))

    if not files:
        print("FAIL  no input files")
        return 2

    bad = 0
    for f in files:
        errs = check_file(f, args.allow_printf)
        if errs:
            bad += 1
            print(f"FAIL  {f}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"PASS  {f}")

    print(f"\n{len(files) - bad}/{len(files)} files passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
