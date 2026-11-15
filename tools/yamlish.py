#!/usr/bin/env python3
"""yamlish.py — 极简 YAML 子集解析器（只覆盖 DSH 插件清单语法）。

用途：在写 `~/.dsh/profiles/*/cordis.patch.yml` 之前先解析回来，确认结构正确。
覆盖范围（够用即可，刻意不支持复杂特性）：
  - 顶层/嵌套序列 `- item`、`- key: value`
  - 映射 `key: value`、`key:` + 缩进块
  - 块标量 `|`、`|-`、`>`、`>-`
  - 单/双引号字符串、普通标量、注释、空行
不支持（遇到即报错）：制表符缩进、锚点/别名、flow 集合 `{...}`、多文档 `---`。

用法:
  python .dsh/tools/yamlish.py <.yml>
  python -c "from yamlish import parse_file; print(parse_file('x.yml'))"
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_INT_RE = re.compile(r"-?\d+")
_FLOAT_RE = re.compile(r"-?\d+\.\d+")


class YamlSubsetError(ValueError):
    pass


def _indent(line: str) -> int:
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            raise YamlSubsetError("缩进中出现制表符（YAML 禁止 tab 缩进）")
        else:
            break
    return n


def _strip_comment(text: str) -> str:
    """去掉行尾注释（忽略引号内的 #）。"""
    out = []
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or text[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(text: str):
    v = text.strip()
    if v == "":
        return None
    if v.startswith("'") and v.endswith("'") and len(v) >= 2:
        return v[1:-1].replace("''", "'")
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        return v[1:-1].replace('\\"', '"')
    if v in ("true", "True", "yes", "on"):
        return True
    if v in ("false", "False", "no", "off"):
        return False
    if v in ("null", "~"):
        return None
    if v.startswith("[") or v.startswith("{"):
        raise YamlSubsetError(f"不支持 flow 集合: {v[:40]}")
    if _INT_RE.fullmatch(v):
        return int(v)
    if _FLOAT_RE.fullmatch(v):
        return float(v)
    return v


def _split_key(text: str):
    """把 `key: value` 拆成 (key, rest)；不是映射行则返回 (None, text)。"""
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
            return text[:i].strip(), text[i + 1 :].strip()
    return None, text


class _Parser:
    def __init__(self, lines: list[tuple[int, str, int]], source: str) -> None:
        self.lines = lines  # (indent, text, lineno)
        self.i = 0
        self.source = source

    def peek(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse_block(self, indent: int):
        item = self.peek()
        if item is None:
            return None
        if item[1].startswith("- "):
            return self.parse_seq(indent)
        return self.parse_map(indent)

    def parse_seq(self, indent: int):
        out = []
        while True:
            item = self.peek()
            if item is None:
                break
            ind, text, ln = item
            if ind < indent:
                break
            if ind > indent:
                raise YamlSubsetError(f"第 {ln} 行缩进异常（期望 {indent}，实际 {ind}）")
            if not text.startswith("- "):
                break
            rest = text[2:].strip()
            self.i += 1
            if rest == "":
                out.append(self.parse_block(indent + 2))
                continue
            key, value = _split_key(rest)
            if key is None:
                out.append(_scalar(rest))
                continue
            # `- key: value` 起一个映射，后续同缩进+2 的键继续
            mapping: dict = {}
            child_indent = indent + 2
            while True:
                if value == "":
                    nxt = self.peek()
                    if nxt is not None and nxt[0] > child_indent:
                        mapping[key] = self._parse_nested(child_indent)
                    elif nxt is not None and nxt[0] == child_indent and nxt[1].startswith("- "):
                        mapping[key] = self.parse_seq(child_indent)
                    else:
                        mapping[key] = None
                elif value[0] in "|>":
                    mapping[key] = self._parse_block_scalar(value, child_indent, indent)
                else:
                    mapping[key] = _scalar(value)
                nxt = self.peek()
                if nxt is None or nxt[0] != child_indent or nxt[1].startswith("- "):
                    break
                k2, v2 = _split_key(nxt[1])
                if k2 is None:
                    raise YamlSubsetError(f"第 {nxt[2]} 行不是合法映射行")
                key, value = k2, v2
                self.i += 1
            out.append(mapping)
        return out

    def _parse_nested(self, parent_indent: int):
        nxt = self.peek()
        assert nxt is not None
        return self.parse_block(nxt[0])

    def _parse_block_scalar(self, marker: str, key_indent: int, parent_indent: int) -> str:
        folded = marker.startswith(">")
        chomp = marker[-1] if len(marker) > 1 and marker[-1] in "+-" else ""
        body: list[str] = []
        block_indent = None
        while True:
            item = self.peek()
            if item is None:
                break
            ind, text, _ln = item
            if ind <= parent_indent:
                break
            if block_indent is None:
                block_indent = ind
            if ind < block_indent:
                break
            body.append(" " * (ind - block_indent) + text)
            self.i += 1
        if folded:
            text = " ".join(x.strip() for x in body)
        else:
            text = "\n".join(body)
        if chomp != "-":
            text += "\n"
        return text

    def parse_map(self, indent: int):
        out: dict = {}
        while True:
            item = self.peek()
            if item is None:
                break
            ind, text, ln = item
            if ind < indent:
                break
            if ind > indent:
                raise YamlSubsetError(f"第 {ln} 行缩进异常（期望 {indent}，实际 {ind}）")
            if text.startswith("- "):
                break
            key, value = _split_key(text)
            if key is None:
                raise YamlSubsetError(f"第 {ln} 行不是合法映射行: {text[:40]!r}")
            if key in out:
                raise YamlSubsetError(f"第 {ln} 行重复键: {key!r}")
            self.i += 1
            if value == "":
                nxt = self.peek()
                if nxt is not None and nxt[0] > indent:
                    out[key] = self.parse_block(nxt[0])
                elif nxt is not None and nxt[0] == indent and nxt[1].startswith("- "):
                    out[key] = self.parse_seq(indent)
                else:
                    out[key] = None
            elif value[0] in "|>":
                out[key] = self._parse_block_scalar(value, indent + 2, indent)
            else:
                out[key] = _scalar(value)
        return out


def parse(text: str, source: str = "<string>") -> object:
    lines: list[tuple[int, str, int]] = []
    for lineno, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if raw.strip() == "":
            continue
        stripped = raw.lstrip(" ")
        if stripped.startswith("#"):
            continue
        ind = _indent(raw)
        content = _strip_comment(raw[ind:])
        if content == "":
            continue
        if content in ("---", "..."):
            raise YamlSubsetError(f"{source}:{lineno}: 不支持多文档标记 {content}")
        lines.append((ind, content, lineno))
    if not lines:
        return None
    p = _Parser(lines, source)
    value = p.parse_block(lines[0][0])
    if p.i != len(p.lines):
        ind, text, ln = p.lines[p.i]
        raise YamlSubsetError(f"{source}:{ln}: 无法解析的剩余内容 {text[:40]!r}")
    return value


def parse_file(path: str | Path) -> object:
    p = Path(path)
    return parse(p.read_text(encoding="utf-8"), source=str(p))


def check_entry_list(value, errors: list[str], at: str = "root") -> None:
    """校验 Cordis 入口列表形态：顶层 list，元素是含 name 的 mapping。"""
    if not isinstance(value, list):
        errors.append(f"{at}: 期望列表，实际 {type(value).__name__}")
        return
    for i, row in enumerate(value):
        if not isinstance(row, dict):
            errors.append(f"{at}[{i}]: 期望映射，实际 {type(row).__name__}")
            continue
        if "insert" in row:
            if not isinstance(row["insert"], list) or not row["insert"]:
                errors.append(f"{at}[{i}].insert: 期望非空列表")
                continue
            for j, ins in enumerate(row["insert"]):
                if not isinstance(ins, dict) or "name" not in ins:
                    errors.append(f"{at}[{i}].insert[{j}]: 缺少 name")
            continue
        if "name" not in row and "id" not in row:
            errors.append(f"{at}[{i}]: 既没有 name 也没有 id")


def lint_preset_patch(value, errors: list[str], known_plugins: set[str] | None = None) -> None:
    """校验「一组 preset 声明」的形状与 id 唯一性，并检查 plugin 名是否在白名单里。"""
    ids: set[str] = set()
    rows: list[dict] = []
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict) and isinstance(entry.get("insert"), list):
                rows.extend(r for r in entry["insert"] if isinstance(r, dict))
            elif isinstance(entry, dict):
                rows.append(entry)
    for row in rows:
        cfg = row.get("config")
        if not isinstance(cfg, dict):
            errors.append(f"preset {row.get('id')!r}: 缺少 config 映射")
            continue
        pid = cfg.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"preset {row.get('id')!r}: config.id 缺失")
        elif pid in ids:
            errors.append(f"preset id 重复: {pid}")
        else:
            ids.add(pid)
        plugins = cfg.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            errors.append(f"preset {pid!r}: config.plugins 必须是非空列表")
            continue
        for p in plugins:
            if not isinstance(p, dict):
                errors.append(f"preset {pid!r}: plugin 项不是映射")
                continue
            pname = p.get("name")
            if not isinstance(pname, str) or not pname:
                errors.append(f"preset {pid!r}: plugin 缺少 name")
            elif known_plugins is not None and pname not in known_plugins:
                errors.append(f"preset {pid!r}: 未知 plugin {pname!r}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法: python yamlish.py <file.yml>")
        return 2
    try:
        value = parse_file(argv[1])
    except YamlSubsetError as e:
        print(f"YAML 子集解析失败: {e}")
        return 1
    import json

    print(json.dumps(value, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
