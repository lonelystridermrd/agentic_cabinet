#!/usr/bin/env python3
"""pipeline_gate.py - mechanical gate for the infra-lib-dev pipeline.

Usage:
  python .dsh/tools/pipeline_gate.py --task iomux --phase requirements
  python .dsh/tools/pipeline_gate.py --task iomux --phase development --changed "a.c b.h"
  python .dsh/tools/pipeline_gate.py --task iomux --init

Exit code 0 = PASS, 1 = FAIL, 2 = usage error.

The gate never trusts a phase's "status" field: it re-derives the verdict from
artifacts on disk. That is the whole point.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:  # Windows console defaults to cp936; keep UTF-8 output readable
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

RUNS = Path(".dsh/runs")
PHASES = [
    "requirements",
    "research",
    "decision",
    "development",
    "review",
    "tests",
    "execution",
]


def fail(msg: str) -> int:
    print(f"FAIL  {msg}")
    return 1


def ok(msg: str) -> int:
    print(f"PASS  {msg}")
    return 0


def load_state(run: Path) -> dict:
    path = run / "run.json"
    if not path.is_file():
        return {"task": run.name, "phases": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(run: Path, state: dict) -> None:
    path = run / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace") if path.is_file() else ""


def first(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def check_requirements(run: Path) -> tuple[bool, str]:
    p = run / "spec.md"
    text = read(p)
    if not text:
        return False, "spec.md 不存在或为空"
    if not first([r"验收标准", r"acceptance"], text):
        return False, "spec.md 缺少「验收标准」段"
    if not first([r"\d", r"ms", r"MB", r"pps", r"条"], text):
        return False, "验收标准没有可量化指标"
    return True, f"spec.md {len(text)} bytes"


def check_research(run: Path) -> tuple[bool, str]:
    reports = sorted((run / "reports").glob("*.md"))
    if not reports:
        return False, "reports/ 下没有调研报告"
    text = read(reports[-1])
    if not first([r"证据", r"evidence"], text):
        return False, f"{reports[-1].name} 缺少证据表"
    if "未实测" not in text and "实测" not in text:
        return False, f"{reports[-1].name} 未声明实测状态"
    cand = len(re.findall(r"^\|\s*\d+\s*\|", text, re.M))
    if cand < 8:
        return False, f"候选表只有 {cand} 行，要求 >=8"
    return True, f"{reports[-1].name} candidates={cand}"


def check_decision(run: Path) -> tuple[bool, str]:
    files = sorted((run / "decisions").glob("*.md"))
    if not files:
        files = sorted(Path(".dsh/knowledge/decisions").glob("dec-*.md"))
    if not files:
        return False, "找不到决策条目"
    target = files[-1]
    text = read(target)
    if not re.search(r"^status:\s*accepted", text, re.M):
        return False, f"{target.name} 不是 accepted"
    if not first([r"反转条件", r"reversal"], text):
        return False, f"{target.name} 缺少反转条件"
    if not first([r"代价", r"consequences"], text):
        return False, f"{target.name} 缺少代价"
    return True, f"{target.name} accepted"


def check_development(run: Path, changed: list[str]) -> tuple[bool, str]:
    if not changed:
        return False, "未提供改动文件列表（--changed）"
    style_dir = run / "style"
    if not style_dir.is_dir():
        return False, "style/ 目录不存在（每文件 style_check 未执行）"
    passed: set[str] = set()
    for log in style_dir.glob("*.log"):
        text = read(log)
        if re.search(r"^FAIL", text, re.M):
            return False, f"{log.name} 存在 FAIL"
        if re.search(r"^PASS", text, re.M):
            passed.add(log.stem)
    want = {Path(p).name for p in changed}
    missing = want - passed
    if missing:
        return False, f"style 未覆盖 {len(missing)} 个文件: {sorted(missing)}"

    comments = run / "comments.log"
    ctext = read(comments)
    m = re.search(r"TOTAL (\d+)/(\d+) commented, (\d+) missing", ctext)
    if not m:
        return False, "comments.log 缺失（comment_audit 未执行）"
    if int(m.group(3)) != 0:
        return False, f"函数注释缺失 {m.group(3)} 个（见 comments.log）"
    return True, f"{len(want)}/{len(want)} files checked, comments 0 missing"


def check_review(run: Path) -> tuple[bool, str]:
    text = read(run / "review.md")
    if not text:
        return False, "review.md 不存在"
    if not re.search(r"P[0-3]", text):
        return False, "review.md 没有 P0–P3 分级"
    return True, "review.md 有分级"


def check_tests(run: Path, spec: str) -> tuple[bool, str]:
    text = read(run / "test-plan.md")
    if not text:
        return False, "test-plan.md 不存在"
    if not first([r"判定", r"通过标准", r"expected"], text):
        return False, "test-plan.md 缺少判定方式"
    n = len(re.findall(r"^\|\s*(TC|T)\d+", text, re.M))
    if n < 1:
        return False, "test-plan.md 没有用例行"
    return True, f"test-plan.md cases={n}"


def check_execution(run: Path) -> tuple[bool, str]:
    text = read(run / "test.log")
    if not text:
        return False, "test.log 不存在"
    if re.search(r"(FAILED|failures=[1-9]|Error [1-9])", text):
        return False, "test.log 含失败"
    if not first([r"\bok\b", r"PASS", r"0 failed", r"success"], text):
        return False, "test.log 没有通过标记"
    msgs = [int(m) for m in re.findall(r"SCALE messages=(\d+)", text)]
    conns = [int(m) for m in re.findall(r"SCALE connections=(\d+)", text)]
    if not msgs or max(msgs) < 100000:
        return False, "test.log 缺少规模证据：SCALE messages= >=100000"
    if not conns or max(conns) < 8000:
        return False, "test.log 缺少规模证据：SCALE connections= >=8000"
    return True, f"test.log clean (messages={max(msgs)}, connections={max(conns)})"


CHECKS = {
    "requirements": lambda run, changed: check_requirements(run),
    "research": lambda run, changed: check_research(run),
    "decision": lambda run, changed: check_decision(run),
    "development": lambda run, changed: check_development(run, changed),
    "review": lambda run, changed: check_review(run),
    "tests": lambda run, changed: check_tests(run, read(run / "spec.md")),
    "execution": lambda run, changed: check_execution(run),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--phase", choices=PHASES)
    ap.add_argument("--changed", default="", help="space separated changed files")
    ap.add_argument("--run-dir", default="", help="override run directory")
    ap.add_argument("--skill", default="", help="skill that produced this phase")
    ap.add_argument("--init", action="store_true")
    args = ap.parse_args()

    run = Path(args.run_dir) if args.run_dir else RUNS / args.task
    if args.init:
        run.mkdir(parents=True, exist_ok=True)
        state = load_state(run)
        state["created"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        save_state(run, state)
        print(f"initialised {run}")
        return 0
    if not args.phase:
        print("usage: --phase required unless --init", file=sys.stderr)
        return 2

    changed = [p for p in args.changed.split() if p]
    ok_flag, detail = CHECKS[args.phase](run, changed)

    state = load_state(run)
    if args.skill:
        state.setdefault("skills", {})[args.phase] = args.skill

    if not state.get("skills", {}).get(args.phase):
        ok_flag = False
        detail += " (no skill recorded: pass --skill)"

    state.setdefault("phases", {})[args.phase] = {
        "passed": ok_flag,
        "detail": detail,
        "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    save_state(run, state)

    return ok(f"{args.phase}: {detail}") if ok_flag else fail(f"{args.phase}: {detail}")


if __name__ == "__main__":
    sys.exit(main())
