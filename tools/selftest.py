#!/usr/bin/env python3
"""selftest.py — kb.py 的自检（不依赖 pytest，纯 unittest + tempfile）。

用法:
  python .dsh/tools/selftest.py -v

覆盖：front-matter 解析、索引/跨类型检索、new 模板生成、promote 守卫、validate 抓错。
所有用例在临时目录内构造最小仓库，不触碰真实 `.dsh/`。
"""

from __future__ import annotations

import importlib.util
import io
import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_COUNTER = itertools.count()

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("kb", HERE / "kb.py")
kb = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(kb)

DECISION = """---
id: dec-2026-11-07-auth-{n}
date: 2026-11-07
context: "认证方案选型 {n}"
decision: "采用 JWT"
alternatives: ["Session", "API Key"]
rationale: "无状态扩展，移动端友好，已有先例"
consequences: ["需处理刷新", "需 JWKS"]
confidence: high
tags: [auth, architecture]
status: proposed
---

## 背景
测试用决策。

## 评估
| 方案 | 扩展性 |
|------|--------|
| JWT | 高 |

## 最终选择
JWT。
"""

EXPERIENCE = """---
id: exp-2026-11-07-auth-{n}
date: 2026-11-07
category: debugging/auth
domain: debugging
problem_type: bug
trigger: "认证 token 过期后未刷新"
symptom: "请求突然 401，且刷新接口本身也 401"
root_cause: "刷新时复用了过期 access token 做鉴权"
fix: "刷新接口改为只校验 refresh token"
prevention: "刷新接口的鉴权只用 refresh token，禁止读 access token。"
tags: [auth, jwt, debugging]
confidence: high
---

## 现象
401 连锁。

## 排查过程
1. 抓包发现刷新请求带了旧 access token。

## 沉淀规则
> 刷新接口的鉴权只用 refresh token，禁止读 access token。
"""

SOP = """---
id: sop-review-auth-audit-{n}
domain: review
name: auth-audit-{n}
version: 1.0
last_updated: 2026-11-07
trigger: "认证相关变更需要审计"
estimated_time: "20min"
---

# 认证审计

## 步骤
1. 查 token 生命周期。

## 检查点
- [ ] refresh 与 access 职责分离
"""

SKILL_OK = """---
name: demo-skill
description: 演示用 Skill，仅用于自检
whenToUse: 用户说"演示一下"
---

# demo

## 触发条件
## 输入
## 步骤
1. 做一件事
## 质量闸门
- [ ] 完成
## 输出格式
文本
## 反面清单
- ❌ 不做
"""

SKILL_NO_TRIGGER = """---
name: bad-skill
description: 缺少 whenToUse 的 Skill
---

# bad
"""


class Base(unittest.TestCase):
    def setUp(self) -> None:
        # 注意：不能放系统 %TEMP%（DSH 沙箱不授予写权限），统一放工作区内临时目录
        scratch = HERE.parent.parent / ".selftest-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        # 不用 tempfile.mkdtemp：其产出目录在 DSH Windows 沙箱内无法再创建子目录（WinError 5），
        # 改用显式 mkdir + 进程号/序号，见 exp-2026-11-07-mkdtemp-sandbox-denied。
        self.tmp = scratch / f"case-{os.getpid()}-{next(_COUNTER)}"
        self.tmp.mkdir(parents=True, exist_ok=False)
        self.repo = kb.Repo(self.tmp)
        d = self.repo.dsh
        for sub in (
            "knowledge/decisions",
            "knowledge/experiences/debugging",
            "knowledge/sops/review",
            "knowledge/.index",
            "tasks/active",
            "tasks/backlog",
            "tasks/done/2026-11",
            "tasks/templates",
            "skills",
            "drafts/skills",
            "agents",
            "schemas",
        ):
            (d / sub).mkdir(parents=True, exist_ok=True)
        for name in ("decision", "experience", "sop", "task", "agent"):
            src = kb.Repo(Path(kb.__file__).resolve().parents[2]).schemas / f"{name}.schema.json"
            if src.is_file():
                shutil.copy(src, d / "schemas" / f"{name}.schema.json")
        shutil.copy(HERE.parent / "tasks" / "templates" / "task-template.md", d / "tasks" / "templates" / "task-template.md")
        (self.tmp / "AGENTS.md").write_text("# test\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def w(self, rel: str, text: str) -> Path:
        p = self.repo.dsh / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class TestFrontmatter(unittest.TestCase):
    def test_inline_list(self):
        data, _ = kb.parse_frontmatter(
            "---\ntags: [a, b-c]\nalt: [\"x, y\", 'z']\n---\nbody\n"
        )
        assert data is not None
        self.assertEqual(data["tags"], ["a", "b-c"])
        self.assertEqual(data["alt"], ["x, y", "z"])

    def test_block_list_strips_quotes(self):
        data, body = kb.parse_frontmatter(
            '---\nsubtasks:\n  - "[ ] 需求澄清"\n  - "  "\n  - "[x] done"\n---\n正文\n'
        )
        assert data is not None
        self.assertEqual(data["subtasks"], ["[ ] 需求澄清", "[x] done"])
        self.assertEqual(body.strip(), "正文")

    def test_bool_and_missing(self):
        data, _ = kb.parse_frontmatter("---\nflag: true\nname: x\n---\n")
        assert data is not None
        self.assertIs(data["flag"], True)
        data2, _ = kb.parse_frontmatter("no frontmatter here\n")
        self.assertIsNone(data2)


class TestIndexAndSearch(Base):
    def _seed(self):
        self.w("knowledge/decisions/dec-2026-11-07-auth-1.md", DECISION.format(n=1))
        self.w("knowledge/experiences/debugging/exp-2026-11-07-auth-1.md", EXPERIENCE.format(n=1))
        self.w("knowledge/sops/review/auth-audit-1.md", SOP.format(n=1))

    def test_cross_type_hit(self):
        self._seed()
        with redirect_stdout(io.StringIO()):
            kb.main(["--root", str(self.tmp), "index"])
        hits = kb.search(self.repo, ["auth"], None, None, None, None, 20)
        types = {e.type for _, e in hits}
        self.assertEqual(types, {"decision", "experience", "sop"})

    def test_type_filter(self):
        self._seed()
        hits = kb.search(self.repo, ["auth"], "decision", None, None, None, 20)
        self.assertTrue(hits)
        self.assertTrue(all(e.type == "decision" for _, e in hits))

    def test_tag_filter(self):
        self._seed()
        hits = kb.search(self.repo, [], None, "jwt", None, None, 20)
        self.assertEqual([e.type for _, e in hits], ["experience"])

    def test_index_counts(self):
        self._seed()
        payload = kb.build_index(self.repo)
        self.assertEqual(payload["counts"], {"decision": 1, "experience": 1, "sop": 1})
        self.assertTrue((self.repo.knowledge / "decisions" / "index.md").is_file())
        self.assertIn("自动生成", (self.repo.knowledge / "decisions" / "index.md").read_text(encoding="utf-8"))


class TestNewAndPromote(Base):
    def test_new_task_uses_template(self):
        with redirect_stdout(io.StringIO()) as buf:
            rc = kb.main(["--root", str(self.tmp), "new", "task", "--title", "重构认证", "--slug", "auth-refactor"])
        self.assertEqual(rc, 0)
        files = list((self.repo.dsh / "tasks" / "backlog").glob("TASK-*-auth-refactor.md"))
        self.assertEqual(len(files), 1)
        data, body = kb.parse_frontmatter(files[0].read_text(encoding="utf-8"))
        assert data is not None
        self.assertEqual(data["title"], "重构认证")
        self.assertNotIn("{date}", files[0].read_text(encoding="utf-8"))
        self.assertIn("[ ] 需求澄清", data["subtasks"])

    def test_new_decision_skeleton_is_deliberately_incomplete(self):
        with redirect_stdout(io.StringIO()):
            kb.main(["--root", str(self.tmp), "new", "decision", "--title", "索引方案", "--slug", "index-plan"])
        f = self.repo.dsh / "knowledge" / "decisions" / "dec-2026-11-07-index-plan.md"
        self.assertTrue(f.is_file(), "应按约定路径生成")
        data, body = kb.parse_frontmatter(f.read_text(encoding="utf-8"))
        assert data is not None
        self.assertIsInstance(data["decision"], str, "空值应落成空字符串而不是空列表")
        self.assertEqual(data["alternatives"], [])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = kb.main(["--root", str(self.tmp), "validate", "--json"])
        self.assertEqual(code, 1, "空骨架必须被校验拦住，防止未填写就入库")
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["errors"])
        self.assertTrue(all("index-plan" in e for e in payload["errors"]), payload["errors"])

    def test_promote_copies_and_refuses_overwrite(self):
        self.w("skills/demo-skill/SKILL.md", SKILL_OK)
        self.w("drafts/skills/demo-skill/SKILL.md", SKILL_OK)
        rc = kb.main(["--root", str(self.tmp), "promote", ".dsh/drafts/skills/demo-skill"])
        self.assertEqual(rc, 1, "同名目标已存在时必须拒绝覆盖")

    def test_promote_new_skill(self):
        self.w("drafts/skills/fresh-skill/SKILL.md", SKILL_OK.replace("demo-skill", "fresh-skill"))
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "promote", str(self.repo.dsh / "drafts" / "skills" / "fresh-skill")])
        self.assertEqual(rc, 0)
        self.assertTrue((self.repo.dsh / "skills" / "fresh-skill" / "SKILL.md").is_file())


class TestValidate(Base):
    def test_detects_missing_when_to_use(self):
        self.w("skills/bad-skill/SKILL.md", SKILL_NO_TRIGGER)
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "validate"])
        self.assertEqual(rc, 1)

    def test_detects_duplicate_id(self):
        self.w("knowledge/decisions/dec-2026-11-07-auth-1.md", DECISION.format(n=1))
        self.w("knowledge/decisions/dec-2026-11-07-auth-1b.md", DECISION.format(n=1))
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "validate"])
        self.assertEqual(rc, 1)

    def test_detects_wrong_agent_schema(self):
        self.w(
            "agents/demo.md",
            "---\nname: demo\ndescription: 演示\nrole: 演示\n"
            "domain: unknown-domain\nmode: read-only\ntools: [read]\noutput_contract: 返回文本\n---\n"
            "## 职责\n## 工作方式\n## 输出格式\n## 边界\n",
        )
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "validate"])
        self.assertEqual(rc, 1)

    def test_clean_repo_passes(self):
        self.w("knowledge/decisions/dec-2026-11-07-auth-1.md", DECISION.format(n=1))
        self.w("skills/demo-skill/SKILL.md", SKILL_OK)
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "validate"])
        self.assertEqual(rc, 0)


class TestPresets(Base):
    CARD = (
        "---\nname: demo-agent\ndescription: 演示用子 Agent，只读审查\nrole: 只读审查者\n"
        "domain: coding\nmode: read-only\ntools: [read, grep, pwsh, web_search]\n"
        "output_contract: 问题清单 + 结论\nescalate_when: 发现秘钥立即停止\nmax_depth: 0\n---\n"
        "## 职责\n读 diff。\n## 工作方式\n只读。\n## 输出格式\n表格。\n## 边界\n不得修改任何文件。\n"
    )
    BOSS = (
        "---\nname: demo-boss\ndescription: 演示用编排 Agent\nrole: 编排者\n"
        "domain: orchestration\nmode: read-write\ntools: [read, subagent]\ncan_write: [\".dsh/**\"]\n"
        "output_contract: 计划 + 摘要\nescalate_when: 越权时停\nmax_depth: 1\n---\n"
        "## 职责\n拆任务。\n## 工作方式\n计划先行。\n## 输出格式\n计划表。\n## 边界\n只写 .dsh。\n"
    )

    def _seed_agents(self):
        self.w("agents/demo-agent.md", self.CARD)
        self.w("agents/demo-boss.md", self.BOSS)

    def test_render_patch_parses_and_composes(self):
        self._seed_agents()
        presets = kb.build_presets(self.repo)
        self.assertEqual([p["id"] for p in presets], ["pcos-demo-agent", "pcos-demo-boss"])
        text = kb.render_patch(presets)
        import yamlish

        value = yamlish.parse(text, source="gen")
        self.assertIsInstance(value, list)
        rows = value[0]["insert"]
        self.assertEqual(len(rows), 2)
        errors: list[str] = []
        yamlish.check_entry_list(value, errors)
        yamlish.lint_preset_patch(value, errors, kb.KNOWN_PLUGINS)
        self.assertEqual(errors, [])
        agent = rows[0]["config"]
        plugins = {p["id"]: p for p in agent["plugins"]}
        self.assertIn("persona", plugins)
        self.assertIn("demo-agent", plugins["persona"]["config"]["prefix"])
        self.assertIn("只读：不得修改任何文件", plugins["persona"]["config"]["prefix"])
        self.assertIn("tool-web", plugins)
        self.assertNotIn("tool-subagent", plugins)
        boss = rows[1]["config"]
        boss_plugins = {p["id"]: p for p in boss["plugins"]}
        self.assertEqual(boss_plugins["tool-subagent"]["config"]["maxDepth"], 1)

    def test_export_writes_and_validates_file(self):
        self._seed_agents()
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "export-presets", "--out", ".dsh/install/p.yml"])
        self.assertEqual(rc, 0)
        self.assertTrue((self.repo.dsh / "install" / "p.yml").is_file())

    def test_apply_and_remove_presets(self):
        self._seed_agents()
        prof = self.tmp / "profile"
        prof.mkdir()
        base = prof / "cordis.patch.yml"
        base.write_text("- id: keep-me\n  name: '@x/y'\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "export-presets", "--out", ".dsh/install/p.yml"])
            self.assertEqual(rc, 0)
            rc = kb.main([
                "--root", str(self.tmp), "apply-presets",
                "--patch", ".dsh/install/p.yml", "--profile-dir", str(prof),
            ])
        self.assertEqual(rc, 0)
        text = base.read_text(encoding="utf-8")
        self.assertIn("# >>> pCOS presets (auto-generated)", text)
        self.assertIn("pcos-demo-agent", text)
        self.assertIn("keep-me", text, "原有条目必须保留")
        with redirect_stdout(io.StringIO()):
            rc = kb.main(["--root", str(self.tmp), "remove-presets", "--profile-dir", str(prof)])
        self.assertEqual(rc, 0)
        after = base.read_text(encoding="utf-8")
        self.assertNotIn("# >>> pCOS presets", after)
        self.assertIn("keep-me", after)

    def test_check_install_reports_missing(self):
        old = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(self.tmp / "fakedsh")
        try:
            with redirect_stdout(io.StringIO()) as buf:
                rc = kb.main(["--root", str(self.tmp), "check-install"])
            self.assertEqual(rc, 1)
            self.assertIn("PROBLEM", buf.getvalue())
        finally:
            if old is None:
                os.environ.pop("DSH_HOME", None)
            else:
                os.environ["DSH_HOME"] = old

    def test_check_install_ok_after_install(self):
        old = os.environ.get("DSH_HOME")
        os.environ["DSH_HOME"] = str(self.tmp / "fakedsh")
        try:
            self.w("skills/demo-skill/SKILL.md", SKILL_OK)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(kb.main(["--root", str(self.tmp), "install", "--scope", "user"]), 0)
            prof = self.tmp / "profile"
            prof.mkdir()
            (prof / "cordis.patch.yml").write_text("- id: keep\n  name: '@x/y'\n", encoding="utf-8")
            self._seed_agents()
            with redirect_stdout(io.StringIO()):
                kb.main(["--root", str(self.tmp), "export-presets", "--out", ".dsh/install/p.yml"])
                rc = kb.main([
                    "--root", str(self.tmp), "apply-presets",
                    "--patch", ".dsh/install/p.yml", "--profile-dir", str(prof),
                ])
            self.assertEqual(rc, 0)
            with redirect_stdout(io.StringIO()) as buf:
                rc = kb.main(["--root", str(self.tmp), "check-install", "--profile-dir", str(prof)])
            self.assertEqual(rc, 0, buf.getvalue())
        finally:
            if old is None:
                os.environ.pop("DSH_HOME", None)
            else:
                os.environ["DSH_HOME"] = old


class TestYamlish(unittest.TestCase):
    def test_rejects_tab_indent(self):
        import yamlish

        with self.assertRaises(yamlish.YamlSubsetError):
            yamlish.parse("- insert:\n\t- id: x\n")

    def test_rejects_flow_collection(self):
        import yamlish

        with self.assertRaises(yamlish.YamlSubsetError):
            yamlish.parse("key: [a]\n")

    def test_block_scalar(self):
        import yamlish

        v = yamlish.parse("a:\n  b: |-\n    line1\n    line2\n  c: 1\n")
        self.assertEqual(v["a"]["b"], "line1\nline2")
        self.assertEqual(v["a"]["c"], 1)

    def test_nested_sequence_of_maps(self):
        import yamlish

        v = yamlish.parse("- insert:\n    - id: x\n      name: 'p/q'\n      config:\n        n: 1\n")
        self.assertEqual(v[0]["insert"][0]["id"], "x")
        self.assertEqual(v[0]["insert"][0]["config"]["n"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
