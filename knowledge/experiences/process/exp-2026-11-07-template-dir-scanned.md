---
id: exp-2026-11-07-template-dir-scanned
date: 2026-11-07
category: process/knowledge-base
domain: process
problem_type: process
trigger: "知识库模板文件放在被扫描的目录树内"
symptom: "kb.py validate 把 task-template.md 当成真实任务卡，报 ID/日期/子任务 8 条错误，index 里也混进一条伪条目"
root_cause: "扫描规则是「目录下所有 *.md」，模板目录同样命中；模板天然带 {date}/{slug} 占位符，必然违反 schema"
fix: "扫描时排除名为 templates 的目录（以及 index.md/readme.md），模板统一放 .dsh/tasks/templates 与 .dsh/docs/templates"
prevention: "新增任何「被扫描的目录树」时，同一次改动里把「非内容目录」加入排除名单，别等校验报警再补。"
tags: [knowledge-base, scanning, tooling, process]
confidence: high
related: [exp-2026-11-07-yaml-quoted-list-items]
---

## 现象

首轮 `kb.py validate` 直接 exit 1，8 条错误全部指向 `.dsh/tasks/templates/task-template.md`：

```
ERROR .dsh/tasks/templates/task-template.md.id: 值 'TASK-{date}-{slug}' 不匹配 ...
ERROR .dsh/tasks/templates/task-template.md: 文件名应等于 ID TASK-{date}-{slug}
```

## 排查过程

1. 错误全部来自模板而非真实条目 → 说明是「扫描范围」问题，不是内容问题。
2. 确认模板必须保留占位符（否则 `kb.py new` 失去意义）→ 不能靠改模板绕过。
3. 定位：`_iter_md` 只过滤了 `index.md`/`readme.md`，没排除 `templates/`。
4. 修：在遍历时排除 `templates` 路径段，重跑后 index 计数从 8 降为 7（正好是 7 条决策）。

## 沉淀规则

> 新增任何「被扫描的目录树」时，同一次改动里把「非内容目录」加入排除名单，别等校验报警再补。

推论：模板与内容必须物理分离（`docs/templates`、`tasks/templates`），且排除规则要写进 `kb.py` 而不是靠命名纪律。
