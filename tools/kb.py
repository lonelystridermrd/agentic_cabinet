#!/usr/bin/env python3
"""kb.py — 个人认知操作系统知识库 CLI（T07 索引与检索入口）。

无第三方依赖，仅用标准库。所有子命令都从 `.dsh/` 的 front-matter 现场扫描，
索引文件只是派生产物，禁止手工维护。

用法:
  python .dsh/tools/kb.py index
  python .dsh/tools/kb.py search 认证 --type decision
  python .dsh/tools/kb.py search "泛型 推导" --tag typescript --json
  python .dsh/tools/kb.py tags
  python .dsh/tools/kb.py stats
  python .dsh/tools/kb.py validate
  python .dsh/tools/kb.py new decision --title "xxx" --slug xxx
  python .dsh/tools/kb.py promote .dsh/drafts/skills/foo
  python .dsh/tools/kb.py log-call --agent code-reviewer --task "审查 X" --status ok

退出码: 0 成功, 1 校验失败, 2 用法错误, 3 环境缺失。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

try:  # Windows 控制台默认 cp936，统一改成 UTF-8，否则中文直接崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - 老解释器或非常规 stdout
    pass

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOMAINS = ("coding", "debugging", "architecture", "process")
SOP_DOMAINS = ("coding", "research", "ops", "review")
TYPE_DIRS = {
    "decision": ("knowledge", "decisions"),
    "experience": ("knowledge", "experiences"),
    "sop": ("knowledge", "sops"),
    "task": ("tasks",),
}

# ---------------------------------------------------------------- 路径


class Repo:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path(__file__).resolve().parents[2]
        self.root = Path(root).resolve()
        self.dsh = self.root / ".dsh"
        self.knowledge = self.dsh / "knowledge"
        self.index_dir = self.knowledge / ".index"
        self.index_json = self.index_dir / "index.json"
        self.schemas = self.dsh / "schemas"

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)


# ---------------------------------------------------------------- front-matter


class FrontMatterError(ValueError):
    pass


def _split_inline_list(raw: str) -> list[str]:
    body = raw.strip()
    if body.startswith("[") and body.endswith("]"):
        body = body[1:-1]
    items: list[str] = []
    buf: list[str] = []
    quote = ""
    for ch in body:
        if quote:
            if ch == quote:
                quote = ""
            buf.append(ch)
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch == ",":
            items.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    items.append("".join(buf))
    return [i.strip().strip("\"'") for i in items if i.strip()]


def _scalar(raw: str):
    v = raw.strip()
    if v == "":
        return ""
    if (v.startswith('"') and v.endswith('"') and len(v) >= 2) or (
        v.startswith("'") and v.endswith("'") and len(v) >= 2
    ):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return _split_inline_list(v)
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    return v


def parse_frontmatter(text: str):
    """返回 (data, body)；没有 front-matter 时返回 (None, text)。"""
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text
    data: dict = {}
    key = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t" and line.lstrip().startswith("- "):
            if key is None:
                continue
            item = line.lstrip()[2:].strip()
            if len(item) >= 2 and item[0] == item[-1] and item[0] in "\"'":
                item = item[1:-1].strip()
            if not item:
                continue
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(item)
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1)
        rest = m.group(2)
        if rest.strip() == "":
            data[key] = []  # 可能是块列表，后续 - 项会追加
        else:
            data[key] = _scalar(rest)
    body = "\n".join(lines[end + 1 :])
    return data, body


def dump_frontmatter(data: dict) -> str:
    out = ["---"]
    for k, v in data.items():
        if isinstance(v, list):
            if not v:
                out.append(f"{k}: []")
                continue
            out.append(f"{k}:")
            for item in v:
                out.append(f"  - {item}")
        elif isinstance(v, bool):
            out.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, str) and (v.strip() == "" or v != v.strip() or ": " in v or v.startswith(("[", "-", "{"))):
            out.append(f'{k}: "{v}"')
        else:
            out.append(f"{k}: {v}")
    out.append("---")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 条目扫描


class Entry:
    __slots__ = ("type", "path", "data", "body", "text")

    def __init__(self, type_: str, path: Path, data: dict, body: str, text: str) -> None:
        self.type = type_
        self.path = path
        self.data = data
        self.body = body
        self.text = text

    @property
    def id(self) -> str:
        raw = self.data.get("id")
        return raw if isinstance(raw, str) else ""

    @property
    def date(self) -> str:
        raw = self.data.get("date")
        if isinstance(raw, str):
            return raw
        for k in ("created", "last_updated"):
            if isinstance(self.data.get(k), str):
                return self.data[k]
        return ""

    @property
    def tags(self) -> list[str]:
        raw = self.data.get("tags")
        return [t for t in raw if isinstance(t, str)] if isinstance(raw, list) else []

    @property
    def title(self) -> str:
        for k in ("decision", "trigger", "title", "name", "symptom"):
            v = self.data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return self.id or self.path.stem

    @property
    def domain(self) -> str:
        v = self.data.get("domain") or self.data.get("category") or ""
        return v if isinstance(v, str) else ""

    def summary(self) -> dict:
        return {
            "type": self.type,
            "id": self.id,
            "date": self.date,
            "title": self.title,
            "domain": self.domain,
            "tags": self.tags,
            "status": self.data.get("status", ""),
            "confidence": self.data.get("confidence", ""),
            "path": self.data.get("__path", ""),
            "bytes": len(self.text.encode("utf-8")),
        }


def _iter_md(path: Path):
    if not path.is_dir():
        return
    for p in sorted(path.rglob("*.md")):
        if p.name.lower() in ("index.md", "readme.md"):
            continue
        if "templates" in p.parts:
            continue
        yield p


PATTERN_KINDS = {"anti-patterns.md": "anti", "good-patterns.md": "good", "recurring-issues.md": "recurring"}


def load_pattern_entries(repo: Repo) -> list[Entry]:
    """patterns/*.md 没有 front-matter，按二级标题切成条目（## <slug>）。"""
    entries: list[Entry] = []
    base = repo.knowledge / "patterns"
    if not base.is_dir():
        return entries
    for p in sorted(base.glob("*.md")):
        if p.name == "index.md":
            continue
        kind = PATTERN_KINDS.get(p.name, "pattern")
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        heads = list(re.finditer(r"^## ([A-Za-z0-9][A-Za-z0-9-]*)\s*$", text, re.M))
        for i, m in enumerate(heads):
            start = m.end()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            section = text[start:end].strip()
            if not section:
                continue
            slug = m.group(1)
            first = next((ln.strip(" -#") for ln in section.splitlines() if ln.strip()), "")
            data = {
                "id": f"pat-{slug}",
                "date": "",
                "title": first,
                "tags": [kind],
                "status": kind,
                "__path": repo.rel(p),
                "__section": section,
            }
            entries.append(Entry("pattern", p, data, section, text))
    return entries


def load_entries(repo: Repo) -> list[Entry]:
    entries: list[Entry] = []
    plan = [
        ("decision", repo.knowledge / "decisions"),
        ("experience", repo.knowledge / "experiences"),
        ("sop", repo.knowledge / "sops"),
        ("task", repo.dsh / "tasks"),
    ]
    for type_, base in plan:
        for p in _iter_md(base):
            if ".index" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            data, body = parse_frontmatter(text)
            if data is None:
                continue
            data = dict(data)
            data["__path"] = repo.rel(p)
            entries.append(Entry(type_, p, data, body, text))
    entries.extend(load_pattern_entries(repo))
    return entries


# ---------------------------------------------------------------- schema 校验


def load_schema(repo: Repo, name: str):
    p = repo.schemas / f"{name}.schema.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _is_type(value, t: str) -> bool:
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def validate_value(value, schema: dict, at: str, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(schema, dict):
        return
    t = schema.get("type")
    if t == "integer" and isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return  # front-matter 里 1 与 "1" 等价，不强制数值类型
    if t and not _is_type(value, t):
        errors.append(f"{at}: 期望 {t}，实际 {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: 值 {value!r} 不在枚举 {schema['enum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{at}: 值 {value!r} 不匹配 {schema['pattern']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{at}: 长度 {len(value)} < {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{at}: 长度 {len(value)} > {schema['maxLength']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{at}: 元素数 {len(value)} < {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{at}: 元素数 {len(value)} > {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(value):
                validate_value(item, schema["items"], f"{at}[{i}]", errors, warnings)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{at}: 缺少必填字段 {key}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                validate_value(value[key], sub, f"{at}.{key}", errors, warnings)
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    warnings.append(f"{at}: 未声明的字段 {key}")


# ---------------------------------------------------------------- index


def build_index(repo: Repo) -> dict:
    entries = load_entries(repo)
    payload = {
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(repo.root),
        "counts": {},
        "entries": [e.summary() for e in entries],
    }
    for e in entries:
        payload["counts"][e.type] = payload["counts"].get(e.type, 0) + 1
    repo.index_dir.mkdir(parents=True, exist_ok=True)
    repo.index_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown_indexes(repo, entries)
    return payload


HEADER = "<!-- 由 .dsh/tools/kb.py index 自动生成，禁止手改；改条目后重跑 kb.py index -->"
SKILL_MANUAL_MARK = "## 备注（手工维护）"


def _table(entries: list[Entry], cols: list[str]) -> list[str]:
    rows = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for e in entries:
        cells = []
        for c in cols:
            if c == "ID":
                cells.append(f"[{e.id}]({Path(e.data['__path']).name})")
            elif c == "日期":
                cells.append(e.date)
            elif c == "标题":
                cells.append(e.title.replace("|", "\\|")[:60])
            elif c == "状态":
                cells.append(str(e.data.get("status", "")))
            elif c == "置信度":
                cells.append(str(e.data.get("confidence", "")))
            elif c == "tags":
                cells.append(", ".join(e.tags))
            elif c == "domain":
                cells.append(e.domain)
            elif c == "问题类型":
                cells.append(str(e.data.get("problem_type", "")))
            elif c == "版本":
                cells.append(str(e.data.get("version", "")))
            else:
                cells.append(str(e.data.get(c, "")))
        rows.append("| " + " | ".join(cells) + " |")
    return rows


def write_markdown_indexes(repo: Repo, entries: list[Entry]) -> None:
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    dec = [e for e in entries if e.type == "decision"]
    exp = [e for e in entries if e.type == "experience"]
    sop = [e for e in entries if e.type == "sop"]

    # 决策
    dec.sort(key=lambda e: (e.date, e.id), reverse=True)
    lines = [HEADER, "", "# 决策索引", "", f"共 {len(dec)} 条 · 生成于 {stamp} · 检索 `python .dsh/tools/kb.py search <关键词>`", ""]
    by_tag: dict[str, list[Entry]] = {}
    for e in dec:
        for t in e.tags or ["untagged"]:
            by_tag.setdefault(t, []).append(e)
    lines += ["## 按 tag", ""]
    for t in sorted(by_tag):
        lines.append(f"- **{t}**（{len(by_tag[t])}）：" + "、".join(f"`{e.id}`" for e in by_tag[t]))
    lines += ["", "## 全部（按日期倒序）", ""]
    lines += _table(dec, ["ID", "日期", "标题", "状态", "置信度", "tags"])
    (repo.knowledge / "decisions" / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 经验
    exp.sort(key=lambda e: (e.domain, e.date, e.id), reverse=False)
    lines = [HEADER, "", "# 经验索引", "", f"共 {len(exp)} 条 · 生成于 {stamp}", "", "分类维度：`domain`（领域，主）× `problem_type`（问题类型，副），见 dec-2026-11-07-g1-experience-taxonomy。", ""]
    for d in DOMAINS:
        group = [e for e in exp if e.domain == d]
        if not group:
            continue
        lines += [f"## {d}（{len(group)}）", ""]
        lines += _table(group, ["ID", "日期", "标题", "问题类型", "置信度", "tags"])
        lines.append("")
    lines += ["## 按问题类型", ""]
    by_type: dict[str, list[Entry]] = {}
    for e in exp:
        by_type.setdefault(str(e.data.get("problem_type", "?")), []).append(e)
    for t in sorted(by_type):
        lines.append(f"- **{t}**（{len(by_type[t])}）：" + "、".join(f"`{e.id}`" for e in by_type[t]))
    (repo.knowledge / "experiences" / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # SOP
    sop.sort(key=lambda e: (e.domain, e.id))
    lines = [HEADER, "", "# SOP 索引", "", f"共 {len(sop)} 条 · 生成于 {stamp}", ""]
    for d in SOP_DOMAINS:
        group = [e for e in sop if e.domain == d]
        if not group:
            continue
        lines += [f"## {d}（{len(group)}）", ""]
        lines += _table(group, ["ID", "标题", "版本", "tags"])
        lines.append("")
    (repo.knowledge / "sops" / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 模式
    pat = [e for e in entries if e.type == "pattern"]
    lines = [HEADER, "", "# 模式索引", "", f"共 {len(pat)} 条 · 生成于 {stamp}", "",
             "来源：`patterns/*.md` 的二级标题；条目 ID 规则 `pat-<slug>`（见命名规范）。", ""]
    for kind, label in (("good", "好模式"), ("anti", "反模式"), ("recurring", "复发问题")):
        group = [e for e in pat if e.data.get("status") == kind]
        if not group:
            continue
        lines += [f"## {label}（{len(group)}）", ""]
        for e in group:
            lines.append(f"- `{e.id}` — {e.title[:60]}  （{Path(e.data['__path']).name}）")
        lines.append("")
    (repo.knowledge / "patterns").mkdir(parents=True, exist_ok=True)
    (repo.knowledge / "patterns" / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- search


def _haystack(e: Entry) -> str:
    extra = ""
    if e.type == "pattern":
        extra = {"anti": " 反模式 反模式库", "good": " 好模式 好模式库", "recurring": " 复发问题 复发"}.get(
            str(e.data.get("status", "")), " 模式"
        )
    return " ".join([e.id, e.title, " ".join(e.tags), e.domain, str(e.data.get("context", "")), extra, e.body]).lower()


def search(repo: Repo, terms: list[str], type_: str | None, tag: str | None, domain: str | None, since: str | None, limit: int):
    entries = load_entries(repo)
    hits = []
    for e in entries:
        if type_ and e.type != type_:
            continue
        if tag and tag not in e.tags:
            continue
        if domain and e.domain != domain:
            continue
        if since and e.date < since:
            continue
        hay = _haystack(e)
        score = 0
        matched_all = True
        for t in terms:
            tl = t.lower()
            if tl in e.tags:
                score += 6
            if tl in e.id.lower() or tl in e.title.lower():
                score += 4
            if tl in hay:
                score += 1
            else:
                matched_all = False
        if terms and not matched_all:
            continue
        hits.append((score, e))
    hits.sort(key=lambda x: (-x[0], x[1].type, x[1].id))
    return hits[:limit]


def cmd_search(repo: Repo, args) -> int:
    terms = [t for t in args.terms if t.strip()]
    hits = search(repo, terms, args.type, args.tag, args.domain, args.since, args.limit)
    if args.json:
        print(json.dumps([dict(score=s, **e.summary()) for s, e in hits], ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"未命中：{' '.join(terms) or '(无关键词)'}  （已扫描 decision/experience/sop/task/pattern）")
        return 0
    by_type: dict[str, list] = {}
    for score, e in hits:
        by_type.setdefault(e.type, []).append((score, e))
    label = {"decision": "决策", "experience": "经验", "sop": "SOP", "task": "任务", "pattern": "模式"}
    print(f"命中 {len(hits)} 条（关键词：{' '.join(terms) or '-'}）")
    for t in ("decision", "experience", "sop", "pattern", "task"):
        group = by_type.get(t)
        if not group:
            continue
        print(f"\n## {label[t]}（{len(group)}）")
        for score, e in group:
            tags = ",".join(e.tags)
            print(f"- [{e.id}] {e.title}  ({e.date or '-'}, score={score}, tags={tags})")
            print(f"  {e.data['__path']}")
    if not args.quiet:
        print("\n提示：命中类型数 =", len(by_type))
    return 0


# ---------------------------------------------------------------- 其它命令


def cmd_board(repo: Repo, args) -> int:
    """从任务卡重建 .dsh/tasks/TRACKING.md 看板（AUTO 区块自动，备注区手工保留）。"""
    tasks = [e for e in load_entries(repo) if e.type == "task"]
    order = {"in_progress": 0, "blocked": 1, "backlog": 2, "done": 3, "cancelled": 4}

    def next_step(body: str) -> str:
        m = re.search(r"^## 下一步\s*$([\s\S]*?)(?=^## |\Z)", body, re.M)
        if not m:
            return ""
        for line in m.group(1).splitlines():
            line = line.strip(" -\t")
            if line:
                return line.replace("|", "\\|")[:40]
        return ""

    def rows(group: list[Entry]) -> list[str]:
        out = ["| ID | 标题 | 优先级 | 下一步 | 更新 |", "|---|---|---|---|---|"]
        for e in group:
            status = str(e.data.get("status", ""))
            files = sorted((repo.dsh / "tasks").rglob(f"{e.path.stem}.md"))
            where = repo.rel(files[0]) if files else "?"
            out.append(
                f"| [{e.id}]({where}) | {e.title} | {e.data.get('priority','')} | "
                f"{next_step(e.body)} | {e.data.get('updated', e.date)} ({status}) |"
            )
        return out

    tasks.sort(key=lambda e: (order.get(str(e.data.get("status")), 9), str(e.data.get("priority", "")), e.id))
    groups = {
        "进行中": [e for e in tasks if e.data.get("status") == "in_progress"],
        "阻塞": [e for e in tasks if e.data.get("status") == "blocked"],
        "待办（backlog）": [e for e in tasks if e.data.get("status") == "backlog"],
        "已完成": [e for e in tasks if e.data.get("status") == "done"],
    }
    lines = ["# 任务看板", "",
             "<!-- 由 kb.py board 自动生成 AUTO 区块；手工备注写在「备注（手工维护）」之后，重建时保留 -->",
             "", "<!-- AUTO:BOARD -->", "",
             f"计数：进行中 {len(groups['进行中'])} · 阻塞 {len(groups['阻塞'])} · 待办 {len(groups['待办（backlog）'])} · 完成 {len(groups['已完成'])}", ""]
    for label, group in groups.items():
        lines += [f"## {label}", ""]
        lines += rows(group) if group else ["（无）"]
        lines.append("")
    lines += ["<!-- /AUTO:BOARD -->", ""]

    path = repo.dsh / "tasks" / "TRACKING.md"
    manual = ""
    if path.is_file():
        old = path.read_text(encoding="utf-8")
        if SKILL_MANUAL_MARK in old:
            manual = old.split(SKILL_MANUAL_MARK, 1)[1]
    lines += [SKILL_MANUAL_MARK, manual.rstrip() or "", ""]
    if not manual.strip():
        lines += ["- 风险：至此无人工记录的阻塞项。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"看板已重建：{repo.rel(path)}（任务 {len(tasks)} 张）")
    return 0


def cmd_tags(repo: Repo, args) -> int:
    entries = load_entries(repo)
    counts: dict[str, int] = {}
    for e in entries:
        for t in e.tags:
            counts[t] = counts.get(t, 0) + 1
    for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{n:3d}  {t}")
    print(f"\n共 {len(counts)} 个 tag / {len(entries)} 条条目")
    return 0


def cmd_stats(repo: Repo, args) -> int:
    entries = load_entries(repo)
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.type] = counts.get(e.type, 0) + 1
    print(json.dumps({"counts": counts, "total": len(entries), "index": str(repo.index_json)}, ensure_ascii=False, indent=2))
    return 0


def cmd_index(repo: Repo, args) -> int:
    payload = build_index(repo)
    print(f"索引已生成：{repo.rel(repo.index_json)}  计数={payload['counts']}")
    for name in ("decisions", "experiences", "sops", "patterns"):
        print(f"  - {repo.rel(repo.knowledge / name / 'index.md')}")
    return 0


def check_skill_dirs(repo: Repo, base: Path, label: str, errors: list[str], warnings: list[str]) -> None:
    if not base.is_dir():
        return
    for skill_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        f = skill_dir / "SKILL.md"
        if not f.is_file():
            warnings.append(f"{repo.rel(skill_dir)}: 目录内没有 SKILL.md（不会被装载）")
            continue
        text = f.read_text(encoding="utf-8")
        data, body = parse_frontmatter(text)
        if data is None:
            errors.append(f"{repo.rel(f)}: 缺少合法 front-matter")
            continue
        name = data.get("name")
        if not isinstance(name, str) or not SLUG_RE.match(name):
            errors.append(f"{repo.rel(f)}: name 必须是 kebab-case，实际 {name!r}")
        elif name != skill_dir.name:
            errors.append(f"{repo.rel(f)}: name {name!r} 与目录名 {skill_dir.name!r} 不一致")
        if not isinstance(data.get("description"), str) or len(str(data.get("description", ""))) < 8:
            errors.append(f"{repo.rel(f)}: description 缺失或过短")
        if not data.get("whenToUse"):
            errors.append(f"{repo.rel(f)}: 缺少 whenToUse（规划要求：没有触发条件的 Skill 不写）")
        for sec in ("## 触发条件", "## 步骤", "## 质量闸门", "## 输出格式", "## 反面清单"):
            if sec not in body:
                warnings.append(f"{repo.rel(f)}: 缺少段落 {sec}")
        size = len(text.encode("utf-8"))
        if size > 8192:
            warnings.append(f"{repo.rel(f)}: {size} 字节 > 8192，超出标准 preset 的工具结果修剪阈值")
        if label == "draft" and name == skill_dir.name:
            warnings.append(f"{repo.rel(f)}: 草稿待确认，可执行 kb.py promote {repo.rel(skill_dir)} 入库")


def cmd_validate(repo: Repo, args) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    entries = load_entries(repo)
    schema_map = {
        "decision": load_schema(repo, "decision"),
        "experience": load_schema(repo, "experience"),
        "sop": load_schema(repo, "sop"),
        "task": load_schema(repo, "task"),
    }
    seen: dict[str, str] = {}
    for e in entries:
        schema = schema_map.get(e.type)
        if schema:
            validate_value(e.data, schema, f"{e.data['__path']}", errors, warnings)
        if not e.id:
            errors.append(f"{e.data['__path']}: 缺少 id")
            continue
        if e.id in seen:
            errors.append(f"重复 ID {e.id}: {seen[e.id]} 与 {e.data['__path']}")
        seen[e.id] = e.data["__path"]
        # 路径与 ID 一致性
        if e.type == "decision" and e.path.stem != e.id:
            errors.append(f"{e.data['__path']}: 文件名应等于 ID {e.id}")
        if e.type == "experience" and e.path.stem != e.id:
            errors.append(f"{e.data['__path']}: 文件名应等于 ID {e.id}")
        if e.type == "experience":
            if e.path.parent.name != e.domain:
                errors.append(f"{e.data['__path']}: 目录 {e.path.parent.name} 与 domain {e.domain} 不一致")
        if e.type == "sop":
            want = e.id[len("sop-"):].split("-", 1)[-1] if e.id.startswith("sop-") else e.id
            if e.path.stem != want:
                errors.append(f"{e.data['__path']}: 文件名 {e.path.stem} 与 SOP slug {want} 不一致")
            if e.path.parent.name != e.domain:
                errors.append(f"{e.data['__path']}: 目录 {e.path.parent.name} 与 domain {e.domain} 不一致")
        if e.type == "task" and e.path.stem != e.id:
            errors.append(f"{e.data['__path']}: 文件名应等于 ID {e.id}")
        # 正文必需段落
        if e.type == "decision":
            for sec in ("## 背景", "## 评估", "## 最终选择"):
                if sec not in e.body:
                    warnings.append(f"{e.data['__path']}: 缺少段落 {sec}")
        if e.type == "experience":
            if "## 沉淀规则" not in e.body:
                warnings.append(f"{e.data['__path']}: 缺少段落 ## 沉淀规则")
        if e.type == "sop" and "## 检查点" not in e.body:
            warnings.append(f"{e.data['__path']}: 缺少段落 ## 检查点")

    # skills（正式 + 草稿沙箱）
    check_skill_dirs(repo, repo.dsh / "skills", "skill", errors, warnings)
    check_skill_dirs(repo, repo.dsh / "drafts" / "skills", "draft", errors, warnings)

    # agents
    agents_dir = repo.dsh / "agents"
    agent_schema = load_schema(repo, "agent")
    if agents_dir.is_dir():
        for f in sorted(agents_dir.glob("*.md")):
            data, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            if data is None:
                errors.append(f"{repo.rel(f)}: 缺少 front-matter")
                continue
            if agent_schema:
                validate_value(data, agent_schema, repo.rel(f), errors, warnings)
            if data.get("name") != f.stem:
                errors.append(f"{repo.rel(f)}: name {data.get('name')!r} 与文件名 {f.stem!r} 不一致")
            for sec in ("## 职责", "## 工作方式", "## 输出格式", "## 边界"):
                if sec not in body:
                    warnings.append(f"{repo.rel(f)}: 缺少段落 {sec}")

    for path in (repo.root / "AGENTS.md",):
        if not path.is_file():
            errors.append("缺少根 AGENTS.md")

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "entries": len(entries)}, ensure_ascii=False, indent=2))
    else:
        for w in warnings:
            print(f"WARN  {w}")
        for e in errors:
            print(f"ERROR {e}")
        print(f"\n条目 {len(entries)} · 错误 {len(errors)} · 警告 {len(warnings)}")
    return 1 if errors else 0


KIND_TEMPLATE = {
    "decision": {
        "dir": ("knowledge", "decisions"),
        "front": {
            "id": "dec-{date}-{slug}",
            "date": "{date}",
            "context": "{title}",
            "decision": "",
            "alternatives": [],
            "rationale": "",
            "consequences": [],
            "confidence": "medium",
            "tags": [],
            "status": "proposed",
        },
    },
    "experience": {
        "dir": ("knowledge", "experiences", "{domain}"),
        "front": {
            "id": "exp-{date}-{slug}",
            "date": "{date}",
            "category": "{category}",
            "domain": "{domain}",
            "problem_type": "bug",
            "trigger": "",
            "symptom": "",
            "root_cause": "",
            "fix": "",
            "prevention": "",
            "tags": [],
            "confidence": "medium",
        },
    },
    "sop": {
        "dir": ("knowledge", "sops", "{domain}"),
        "front": {
            "id": "sop-{domain}-{slug}",
            "domain": "{domain}",
            "name": "{slug}",
            "version": "0.1",
            "last_updated": "{date}",
            "trigger": "",
            "estimated_time": "",
        },
    },
}


def cmd_new(repo: Repo, args) -> int:
    today = _dt.date.today().isoformat()
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")
    if not slug or not SLUG_RE.match(slug):
        print(f"错误：无法从标题推导 slug，请用 --slug 指定 kebab-case 标识（收到 {slug!r}）", file=sys.stderr)
        return 2
    domain = args.domain or "coding"
    if args.kind == "task":
        tpl = (repo.dsh / "tasks" / "templates" / "task-template.md")
        if not tpl.is_file():
            print(f"错误：缺少任务模板 {repo.rel(tpl)}", file=sys.stderr)
            return 3
        text = tpl.read_text(encoding="utf-8").format(date=today, slug=slug, title=args.title)
        dest = repo.dsh / "tasks" / "backlog" / f"TASK-{today}-{slug}.md"
    elif args.kind in KIND_TEMPLATE:
        spec = KIND_TEMPLATE[args.kind]
        parts = [p.format(domain=domain) for p in spec["dir"]]
        base = repo.dsh.joinpath(*parts)
        base.mkdir(parents=True, exist_ok=True)
        front = {}
        for k, v in spec["front"].items():
            if isinstance(v, str):
                front[k] = v.format(date=today, slug=slug, title=args.title, domain=domain,
                                    category=f"{domain}/general")
            else:
                front[k] = list(v)
        name = f"{front['id']}.md" if args.kind != "sop" else f"{slug}.md"
        dest = base / name
        body = TPL_BODY[args.kind]
        if dest.exists():
            print(f"错误：目标已存在 {repo.rel(dest)}", file=sys.stderr)
            return 2
        dest.write_text(dump_frontmatter(front) + "\n" + body, encoding="utf-8")
        print(f"已创建 {repo.rel(dest)}")
        return 0
    else:
        print(f"未知类型 {args.kind}", file=sys.stderr)
        return 2
    if dest.exists():
        print(f"错误：目标已存在 {repo.rel(dest)}", file=sys.stderr)
        return 2
    dest.write_text(text, encoding="utf-8")
    print(f"已创建 {repo.rel(dest)}")
    return 0


TPL_BODY = {
    "decision": """
# 决策

## 背景
（为什么现在必须定）

## 评估
| 方案 | 维度A | 维度B |
|------|-------|-------|
| A | | |
| B | | |

## 最终选择
（选了什么 + 关键理由）

## 后果与代价
- 

## 置信度理由
（高/中/低的具体依据）
""",
    "experience": """
## 现象
（可观察的失败表现）

## 排查过程
1. 

## 沉淀规则
> 一句话可执行规则：
""",
    "sop": """
## 步骤
1. 

## 检查点
- [ ] 
""",
}


def cmd_promote(repo: Repo, args) -> int:
    raw = Path(args.draft)
    src = (raw if raw.is_absolute() else repo.root / raw).resolve()
    if not src.exists():
        print(f"错误：草稿不存在 {src}", file=sys.stderr)
        return 3
    if src.is_dir():
        skill_dir = src
    else:
        skill_dir = src.parent
    f = skill_dir / "SKILL.md"
    if not f.is_file():
        print(f"错误：{repo.rel(skill_dir)} 内没有 SKILL.md", file=sys.stderr)
        return 3
    data, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
    if data is None or not isinstance(data.get("name"), str):
        print("错误：SKILL.md 缺少合法 front-matter", file=sys.stderr)
        return 1
    name = data["name"]
    if not SLUG_RE.match(name):
        print(f"错误：skill name {name!r} 不是 kebab-case", file=sys.stderr)
        return 1
    dest = repo.dsh / "skills" / name
    if dest.exists():
        print(f"错误：目标已存在 {repo.rel(dest)}，先人工决定覆盖或更名", file=sys.stderr)
        return 1
    shutil.copytree(skill_dir, dest)
    print(f"已入库 {repo.rel(dest)}（草稿保留在 {repo.rel(skill_dir)}，确认后可删）")
    return 0


def cmd_log_call(repo: Repo, args) -> int:
    log = repo.knowledge / "agent-calls" / f"{_dt.date.today().isoformat()}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent": args.agent,
        "task": args.task,
        "status": args.status,
        "session": os.environ.get("DSH_SESSION_ID", ""),
        "note": args.note or "",
    }
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"已追加调用日志 {repo.rel(log)}")
    return 0


# ---------------------------------------------------------------- 安装到 DSH

# 这些名字与 DSH 内置 preset（standard/cordis/minimal/ptc/review）里出现的插件名一致，
# 不自己发明名字，避免启动期激活失败。
PLUGIN_MAP = {
    "read": ("tool-fs", "@deepseek-ai/dsh-tool-fs", None),
    "write": ("tool-fs", "@deepseek-ai/dsh-tool-fs", None),
    "edit": ("tool-fs", "@deepseek-ai/dsh-tool-fs", None),
    "grep": ("tool-fs-search", "@deepseek-ai/dsh-tool-fs-search", None),
    "glob": ("tool-fs-search", "@deepseek-ai/dsh-tool-fs-search", None),
    "pwsh": ("tool-pwsh", "@deepseek-ai/dsh-tool-pwsh", None),
    "web_search": ("tool-web", "@deepseek-ai/dsh-tool-web", {"fetch": True, "searchTimeoutMs": 60000}),
    "web_fetch": ("tool-web", "@deepseek-ai/dsh-tool-web", {"fetch": True, "searchTimeoutMs": 60000}),
    "todo_write": ("tool-todo", "@deepseek-ai/dsh-tool-todo", {"allowParallelInProgress": True}),
    "present": ("tool-present", "@deepseek-ai/dsh-tool-present", None),
}
KNOWN_PLUGINS = {
    "@deepseek-ai/dsh-persona",
    "@deepseek-ai/dsh-agent-instructions",
    "@deepseek-ai/dsh-time-context",
    "@deepseek-ai/dsh-tool-fs",
    "@deepseek-ai/dsh-tool-fs-search",
    "@deepseek-ai/dsh-tool-pwsh",
    "@deepseek-ai/dsh-tool-web",
    "@deepseek-ai/dsh-tool-todo",
    "@deepseek-ai/dsh-tool-present",
    "@deepseek-ai/dsh-tool-skill",
    "@deepseek-ai/dsh-skill-filesystem",
    "@deepseek-ai/dsh-tool-subagent",
}


def _q(text: str) -> str:
    """单引号标量，内部单引号翻倍。"""
    return "'" + str(text).replace("'", "''") + "'"


def _persona_text(card: Data) -> str:
    data = card.data
    name = data.get("name", "")
    role = str(data.get("role", "")).strip()
    mode = str(data.get("mode", "read-only"))
    lines = [
        f"你是 `{name}`：{role}",
        "",
        "工作方式：",
        "- 开工前若工作区存在 `.dsh/agents/%s.md`，先读它（完整职责、工作方式、输出格式）；不存在则按本提示执行。" % name,
        "- 需要历史决策/经验时用 `python .dsh/tools/kb.py search <关键词>`，引用条目 ID，不要凭记忆。",
    ]
    if mode == "read-only":
        lines += [
            "- 只读：不得修改任何文件，不得执行有副作用的命令（删除、安装、checkout、reset、push）。",
            "- 结论必须带证据（文件:行 / 命令输出），不确定就标注「待确认」。",
        ]
    else:
        wl = data.get("can_write")
        allow = "、".join(wl) if isinstance(wl, list) and wl else "无（需回到主会话确认）"
        lines += [
            f"- 写权限仅限：{allow}；超出范围一律停手，回主会话要授权。",
        ]
    esc = data.get("escalate_when")
    if esc:
        lines += ["", f"停手条件：{esc}"]
    contract = data.get("output_contract")
    if contract:
        lines += ["", f"输出契约：{contract}"]
    return "\n".join(lines)


def _plugin_rows(card: Data) -> list[dict]:
    data = card.data
    tools = [t for t in data.get("tools", []) if isinstance(t, str)] if isinstance(data.get("tools"), list) else []
    rows: list[dict] = [
        {"id": "persona", "name": "@deepseek-ai/dsh-persona", "config": {"prefix": _persona_text(card)}},
        {"id": "agent-instructions", "name": "@deepseek-ai/dsh-agent-instructions", "config": {"maxBytes": 65536}},
        {"id": "time-context", "name": "@deepseek-ai/dsh-time-context"},
    ]
    seen: set[str] = set()
    for t in tools:
        spec = PLUGIN_MAP.get(t)
        if spec is None or spec[0] in seen:
            continue
        seen.add(spec[0])
        row: dict = {"id": spec[0], "name": spec[1]}
        if spec[2]:
            row["config"] = dict(spec[2])
        rows.append(row)
    # 每个 agent 都能用 Skill（这是本系统的核心）
    if "tool-skill" not in seen:
        rows.append({"id": "skill-filesystem", "name": "@deepseek-ai/dsh-skill-filesystem"})
        rows.append({"id": "tool-skill", "name": "@deepseek-ai/dsh-tool-skill"})
    depth = data.get("max_depth")
    can_delegate = str(depth) not in ("0", "None", "") and "subagent" in tools
    if can_delegate:
        rows.append(
            {
                "id": "tool-subagent",
                "name": "@deepseek-ai/dsh-tool-subagent",
                "config": {"provider": "spawn", "toolName": "subagent", "maxDepth": int(str(depth))},
            }
        )
    return rows


def build_presets(repo: Repo) -> list[dict]:
    agents_dir = repo.dsh / "agents"
    presets: list[dict] = []
    cards = []
    if agents_dir.is_dir():
        for f in sorted(agents_dir.glob("*.md")):
            data, _body = parse_frontmatter(f.read_text(encoding="utf-8"))
            if data is None or not data.get("name"):
                continue
            cards.append(Data(data, f.read_text(encoding="utf-8")))
    for i, card in enumerate(cards):
        name = str(card.data["name"])
        desc = str(card.data.get("description", ""))[:120]
        presets.append(
            {
                "loader_id": f"preset-pcos-{name}",
                "id": f"pcos-{name}",
                "name": f"pcos · {name}",
                "description": desc,
                "order": 100 + i,
                "plugins": _plugin_rows(card),
            }
        )
    return presets


class Data:
    __slots__ = ("data", "text")

    def __init__(self, data: dict, text: str) -> None:
        self.data = data
        self.text = text


def _emit_plugins(plugins: list[dict], indent: int) -> list[str]:
    pad = " " * indent
    out: list[str] = []
    for p in plugins:
        out.append(f"{pad}- id: {p['id']}")
        out.append(f"{pad}  name: {_q(p['name'])}")
        cfg = p.get("config")
        if isinstance(cfg, dict):
            if len(cfg) == 1 and isinstance(next(iter(cfg.values())), str) and "\n" in str(next(iter(cfg.values()))):
                # 单键且是多行文本 -> 块标量
                key, val = next(iter(cfg.items()))
                out.append(f"{pad}  config:")
                out.append(f"{pad}    {key}: |-")
                for line in str(val).split("\n"):
                    out.append(f"{pad}      {line}".rstrip())
                continue
            out.append(f"{pad}  config:")
            for k, v in cfg.items():
                if isinstance(v, bool):
                    out.append(f"{pad}    {k}: {'true' if v else 'false'}")
                elif isinstance(v, int):
                    out.append(f"{pad}    {k}: {v}")
                else:
                    out.append(f"{pad}    {k}: {_q(v)}")
    return out


def render_patch(presets: list[dict]) -> str:
    out = [
        "# ────────────────────────────────────────────────────────────────",
        "# pCOS agent presets — 由 `python .dsh/tools/kb.py export-presets` 自动生成",
        "# 不要手改；改 `.dsh/agents/*.md` 后重跑导出。",
        "# 应用：追加到 <DSH_HOME>/profiles/<profile>/cordis.patch.yml 末尾，然后重启 DSH。",
        "# 移除：删除本文件中以 AUTO-PCOS 标记包围的整段。",
        "# ────────────────────────────────────────────────────────────────",
        "- insert:",
    ]
    for p in presets:
        out += [
            f"    - id: {p['loader_id']}",
            "      name: '@deepseek-ai/dsh-agent-preset'",
            "      config:",
            f"        id: {p['id']}",
            f"        name: {_q(p['name'])}",
            f"        description: {_q(p['description'])}",
            f"        order: {p['order']}",
            "        plugins:",
        ]
        out += _emit_plugins(p["plugins"], 10)
    return "\n".join(out) + "\n"


def cmd_export_presets(repo: Repo, args) -> int:
    import yamlish

    presets = build_presets(repo)
    if args.only:
        keep = {s.strip() for s in args.only.split(",") if s.strip()}
        presets = [p for p in presets if p["id"] in keep or p["id"].removeprefix("pcos-") in keep]
    text = render_patch(presets)
    out = Path(args.out)
    if not out.is_absolute():
        out = repo.root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    errors: list[str] = []
    try:
        value = yamlish.parse(text, source=repo.rel(out))
    except yamlish.YamlSubsetError as e:
        print(f"错误：生成的补丁无法被解析 → {e}", file=sys.stderr)
        return 1
    yamlish.check_entry_list(value, errors)
    yamlish.lint_preset_patch(value, errors, KNOWN_PLUGINS)
    # 唯一性：preset id 与 loader id
    loader_ids = [p["loader_id"] for p in presets]
    if len(set(loader_ids)) != len(loader_ids):
        errors.append("loader id 重复")
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(f"已导出 {len(presets)} 个 preset → {repo.rel(out)}（自校验通过：YAML 可解析、插件名在白名单内）")
    for p in presets:
        print(f"  - {p['id']:<28} {p['name']}")
    return 0


def cmd_install(repo: Repo, args) -> int:
    """把 .dsh/skills 复制到 DSH 的用户级/指定 skill 根，并写安装清单。"""
    if args.scope == "user":
        home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
        target = home / "skills"
    else:
        target = repo.root / args.target if args.target else repo.dsh / "skills"
    src = repo.dsh / "skills"
    if not src.is_dir():
        print(f"错误：{repo.rel(src)} 不存在", file=sys.stderr)
        return 3
    names = sorted(p.name for p in src.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if args.dry_run:
        print(f"[dry-run] 将安装 {len(names)} 个 Skill → {target}")
        for n in names:
            print(f"  - {n}")
        return 0
    target.mkdir(parents=True, exist_ok=True)
    installed = []
    for n in names:
        dst = target / n
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src / n, dst)
        installed.append(n)
    manifest = {
        "installed_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": args.scope,
        "target": str(target),
        "source": repo.rel(src),
        "skills": installed,
    }
    mpath = repo.dsh / "install" / "manifest-skills.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已安装 {len(installed)} 个 Skill → {target}")
    print(f"清单：{repo.rel(mpath)}")
    print("DSH 会监视该目录，新会话（或下一次目录刷新）即可见；无需重启。")
    return 0


def _profile_dir(args) -> Path:
    if args.profile_dir:
        return Path(args.profile_dir)
    home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
    profile = os.environ.get("DSH_PROFILE", "desktop")
    return home / "profiles" / profile


def cmd_apply_presets(repo: Repo, args) -> int:
    """把导出的 preset 补丁追加到 profile 的 cordis.patch.yml（带备份 + 回滚说明）。"""
    import yamlish

    patch = Path(args.patch)
    if not patch.is_absolute():
        patch = repo.root / patch
    if not patch.is_file():
        print(f"错误：补丁文件不存在 {patch}", file=sys.stderr)
        return 3
    block = patch.read_text(encoding="utf-8").split("# ────────────────────────────────────────────────────────────────\n", 2)
    body = patch.read_text(encoding="utf-8")
    if "AUTO-PCOS" not in body:
        body = body  # 标记仅用于文档说明，不强制
    prof = _profile_dir(args)
    target = prof / "cordis.patch.yml"
    if not prof.is_dir():
        print(f"错误：profile 目录不存在 {prof}", file=sys.stderr)
        return 3
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    begin, end = "# >>> pCOS presets (auto-generated)", "# <<< pCOS presets (auto-generated)"
    if begin in existing:
        print("已存在 pCOS preset 区块；先用 `--remove` 移除再重新应用。", file=sys.stderr)
        return 1

    backup_dir = repo.dsh / "install" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"cordis.patch.yml.{stamp}.bak"
    backup.write_text(existing, encoding="utf-8")

    merged = existing.rstrip("\n") + "\n\n" + begin + "\n" + body.rstrip("\n") + "\n" + end + "\n"
    try:
        value = yamlish.parse(merged, source=str(target))
    except yamlish.YamlSubsetError as e:
        print(f"错误：合并后的 profile 补丁无法解析，已中止 → {e}", file=sys.stderr)
        return 1
    errors: list[str] = []
    yamlish.check_entry_list(value, errors)
    preset_rows = 0
    for row in value if isinstance(value, list) else []:
        for ins in row.get("insert", []) if isinstance(row, dict) else []:
            if isinstance(ins, dict) and isinstance(ins.get("config"), dict) and str(ins["config"].get("id", "")).startswith("pcos-"):
                preset_rows += 1
    if errors or preset_rows == 0:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        print("错误：合并结果校验失败，已中止（profile 未改动）", file=sys.stderr)
        return 1

    target.write_text(merged, encoding="utf-8")
    print(f"已写入 {preset_rows} 个 preset → {target}")
    print(f"备份：{repo.rel(backup)}")
    print(f"回滚：Remove-Item '{target}' -Force; Copy-Item '{backup}' '{target}'")
    print("生效需要重启 DeepSeek Harness（profile 补丁在启动时加载）。")
    return 0


def cmd_remove_presets(repo: Repo, args) -> int:
    import yamlish

    prof = _profile_dir(args)
    target = prof / "cordis.patch.yml"
    if not target.is_file():
        print(f"错误：{target} 不存在", file=sys.stderr)
        return 3
    text = target.read_text(encoding="utf-8")
    begin, end = "# >>> pCOS presets (auto-generated)", "# <<< pCOS presets (auto-generated)"
    if begin not in text or end not in text:
        print("未发现 pCOS preset 区块，无需移除。")
        return 0
    head, rest = text.split(begin, 1)
    _mid, tail = rest.split(end, 1)
    backup_dir = repo.dsh / "install" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (backup_dir / f"cordis.patch.yml.{stamp}.before-remove.bak").write_text(text, encoding="utf-8")
    target.write_text(head.rstrip("\n") + "\n" + tail.lstrip("\n"), encoding="utf-8")
    yamlish.parse(target.read_text(encoding="utf-8"), source=str(target))
    print(f"已移除 pCOS preset 区块 → {target}（重启后生效）")
    return 0


def cmd_check_install(repo: Repo, args) -> int:
    """核对安装结果：用户级 Skill 是否齐全、profile 里是否还有 preset 区块。"""
    import yamlish

    problems: list[str] = []
    home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
    skills_target = home / "skills"
    src = repo.dsh / "skills"
    want = sorted(p.name for p in src.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()) if src.is_dir() else []
    got = sorted(p.name for p in skills_target.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()) if skills_target.is_dir() else []
    missing = [n for n in want if n not in got]
    stale = []
    for n in want:
        if n in got and (src / n / "SKILL.md").read_text(encoding="utf-8") != (skills_target / n / "SKILL.md").read_text(encoding="utf-8"):
            stale.append(n)
    if missing:
        problems.append(f"用户级 Skill 缺失 {len(missing)} 个：{', '.join(missing[:5])}")
    if stale:
        problems.append(f"用户级 Skill 与工作区不一致（需重跑 install）：{', '.join(stale[:5])}")

    prof = _profile_dir(args)
    target = prof / "cordis.patch.yml"
    presets: list[str] = []
    if not target.is_file():
        problems.append(f"profile 补丁不存在：{target}")
    else:
        try:
            value = yamlish.parse(target.read_text(encoding="utf-8"), source=str(target))
        except yamlish.YamlSubsetError as e:
            problems.append(f"profile 补丁无法解析：{e}")
            value = []
        for row in value if isinstance(value, list) else []:
            for ins in row.get("insert", []) if isinstance(row, dict) else []:
                if isinstance(ins, dict) and isinstance(ins.get("config"), dict):
                    pid = str(ins["config"].get("id", ""))
                    if pid.startswith("pcos-"):
                        presets.append(pid)
        if not presets:
            problems.append("profile 里没有 pcos preset 区块（可能被 DSH 重写；重跑 apply-presets）")

    print(f"用户级 Skill：{len(got)}/{len(want)} 在 {skills_target}")
    print(f"agent preset：{len(presets)} 个在 {target}")
    if presets:
        print("  " + ", ".join(presets))
    if problems:
        for p in problems:
            print(f"PROBLEM {p}")
        return 1
    print("安装状态：OK")
    return 0


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kb.py", description="个人认知操作系统知识库 CLI")
    p.add_argument("--root", help="工作区根目录（默认由脚本位置推导）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("index", help="重建 JSON + markdown 索引")
    sp.set_defaults(func=cmd_index)

    sp = sub.add_parser("board", help="从任务卡重建 tasks/TRACKING.md 看板")
    sp.set_defaults(func=cmd_board)

    sp = sub.add_parser("install", help="把 Skill 安装到 DSH 的 skill 根（用户级/指定目录）")
    sp.add_argument("--scope", choices=["user", "project"], default="user")
    sp.add_argument("--target", help="scope=project 时的目标目录")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_install)

    sp = sub.add_parser("export-presets", help="把 agents/*.md 导出成 DSH agent preset 补丁")
    sp.add_argument("--out", default=".dsh/install/dsh-agent-presets.patch.yml")
    sp.add_argument("--only", help="只导出这些名字（逗号分隔）")
    sp.set_defaults(func=cmd_export_presets)

    sp = sub.add_parser("apply-presets", help="把 preset 补丁追加到 profile 的 cordis.patch.yml（需重启）")
    sp.add_argument("--patch", default=".dsh/install/dsh-agent-presets.patch.yml")
    sp.add_argument("--profile-dir")
    sp.set_defaults(func=cmd_apply_presets)

    sp = sub.add_parser("remove-presets", help="移除 profile 里的 pCOS preset 区块")
    sp.add_argument("--profile-dir")
    sp.set_defaults(func=cmd_remove_presets)

    sp = sub.add_parser("check-install", help="核对 Skill 与 preset 的安装状态")
    sp.add_argument("--profile-dir")
    sp.set_defaults(func=cmd_check_install)

    sp = sub.add_parser("search", help="按关键词/tag/domain 检索")
    sp.add_argument("terms", nargs="*")
    sp.add_argument("--type", choices=["decision", "experience", "sop", "task"])
    sp.add_argument("--tag")
    sp.add_argument("--domain")
    sp.add_argument("--since")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--quiet", action="store_true")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("tags", help="tag 频次")
    sp.set_defaults(func=cmd_tags)

    sp = sub.add_parser("stats", help="条目统计")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("validate", help="schema + 命名 + Skill/Agent 一致性校验")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("new", help="按模板新建条目")
    sp.add_argument("kind", choices=["decision", "experience", "sop", "task"])
    sp.add_argument("--title", required=True)
    sp.add_argument("--slug")
    sp.add_argument("--domain", default="coding")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("promote", help="把沙箱草稿迁入 .dsh/skills（G3）")
    sp.add_argument("draft")
    sp.set_defaults(func=cmd_promote)

    sp = sub.add_parser("log-call", help="记录一次子 Agent 派发（T06）")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--task", required=True)
    sp.add_argument("--status", choices=["ok", "fail", "blocked"], default="ok")
    sp.add_argument("--note")
    sp.set_defaults(func=cmd_log_call)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Repo(Path(args.root) if args.root else None)
    if not repo.dsh.is_dir():
        print(f"错误：{repo.dsh} 不存在，先执行 T01 建骨架", file=sys.stderr)
        return 3
    return args.func(repo, args)


if __name__ == "__main__":
    raise SystemExit(main())
