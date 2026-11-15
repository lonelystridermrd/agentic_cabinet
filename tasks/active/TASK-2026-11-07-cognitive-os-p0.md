---
id: TASK-2026-11-07-cognitive-os-p0
title: 认知操作系统阶段 0（T01–T08）
status: in_progress
priority: P0
created: 2026-11-07
updated: 2026-11-07
domain: process/knowledge-system
related_decisions: [dec-2026-11-07-g1-experience-taxonomy, dec-2026-11-07-g2-agents-md-limit, dec-2026-11-07-g3-draft-promote-gate, dec-2026-11-07-g4-confidence-scale, dec-2026-11-07-g5-code-snippet-policy, dec-2026-11-07-g6-index-strategy, dec-2026-11-07-g7-drill-task-scope]
related_experiences: [exp-2026-11-07-gbk-python-stdout, exp-2026-11-07-asar-offset-relative, exp-2026-11-07-yaml-quoted-list-items, exp-2026-11-07-template-dir-scanned]
subtasks:
  - "[x] T01 目录骨架与命名规范"
  - "[x] T02 AGENTS.md 行为契约"
  - "[x] T04 decision-logger + G1–G7 决策条目"
  - "[x] T05 experience-capture + 真实经验"
  - "[x] T03 make-skill 元技能"
  - "[x] T06 bootstrap 编排 Skill + persona"
  - "[x] T07 kb.py 索引与检索入口"
  - "[x] P1–P3 领域 Skill 与子 Agent 卡片"
  - "[x] T08 闭环演练验收（检索跨类型命中 + 次日召回）"
  - "[x] 安装到 DSH：15 Skill → 用户级根，17 Agent → profile preset 区块"
  - "[ ] 重启后确认 17 个 pcos preset 在 agent 列表中可用"
  - "[ ] G1–G7 用户确认，status 转 accepted"
---

# 认知操作系统阶段 0（T01–T08）

## 目标

在 `.dsh/` 内建立可持续演进的知识库 + Skill + 子 Agent 体系，并通过「执行 → 记录 → 次日召回」全链路验收。

## 非目标

- 不引入向量检索（G6：条目 <200 前不做）
- 不修改 DSH profile 插件树（子 Agent 用 persona 卡片 + 派发协议实现）
- 不写业务代码

## 验收标准

1. `python .dsh/tools/kb.py validate` 0 error。
2. `kb.py search <关键词>` 能同时命中 decision + experience + sop 三类。
3. 每个 Skill 有 `whenToUse`、每张 Agent 卡片通过 schema。
4. daily-log 的「明日召回」在下次会话被 `bootstrap` 启动规程引用。

## 进度日志

### 2026-11-07

- 完成 T01–T07 与领域 Skill/Agent 落地。
- 真实卡点 6 个，全部按 `experience-capture` 入库（其中 2 个由自检脚本主动发现）。
- 7 条闸门决策以 `proposed` 落库，等用户确认。
- T08 演练完成：`kb.py stats` = 7 决策 / 6 经验 / 5 SOP / 2 任务 / 8 模式；`search 扫描` 命中 3 类；`validate` 0 error；`selftest` 15/15 OK。记录见 `.dsh/docs/T08-闭环演练记录.md`。
- 安装到 DSH（dec-2026-11-07-g8-install-strategy）：15 个 Skill 复制到 `%DSH_HOME%\skills`（免重启）；17 个 Agent 由 `export-presets` 生成 preset 声明，`apply-presets` 带备份写入 profile（已写入 17 条，合并后 YAML 自校验通过）。`check-install` = OK。生效待重启。

## 阻塞项

无（G1–G7 待用户确认，不阻塞 P1 准备）

## 下一步

- 跑 T08 验收命令并留证
- 邀请用户逐条确认 G1–G7
