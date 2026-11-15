---
name: task-tracker
description: 维护任务卡全生命周期：建卡、改状态、移目录、归档，并同步 .dsh/tasks/TRACKING.md 看板。适用"建个任务""这个做完了""更新看板""归档一下"。
whenToUse: 用户说"建个任务卡""把这件事记下来推进""标记完成""归档""看板更新一下"；或任务状态/优先级发生变化而卡片没跟上。
---

# task-tracker — 任务卡生命周期

## 触发条件

- 新任务需要落到 `backlog/` 或 `active/`
- 任务状态变化：`backlog`/`in_progress`/`blocked`/`done`/`cancelled`
- 需要归档到 `done/YYYY-MM/` 或同步 `TRACKING.md`

**不触发**：纯知识条目（走 `decision-logger`/`experience-capture`）；一次对话内的临时 TODO（先留在回复里，出现第 2 次再建卡）。

## 输入

- 标题（一句话，完成后什么变了）
- 优先级 `P0`–`P3` 与领域 `domain`
- 验收判据（写不出就不建卡）
- 关联 `dec-*`/`exp-*`（有则填，无则留空数组）

## 步骤

1. **查重**：`python .dsh/tools/kb.py search <关键词> --type task`。
   **完成判据**：同主题在办卡 → 只追加 `subtasks`，不新建；无命中才进入下一步。
2. **建卡**：`python .dsh/tools/kb.py new task --title "<标题>" --slug <kebab-case> --domain <domain>`。
   **完成判据**：文件出现在 `.dsh/tasks/backlog/TASK-YYYY-MM-DD-<slug>.md`，ID 与文件名一致。
3. **补 front-matter**：`priority`、`related_decisions`、`related_experiences`、`subtasks`；`subtasks` ≥1 且每行形如 `[ ] 动作`。
   **完成判据**：`python .dsh/tools/kb.py validate` 对该卡零 error。
4. **状态流转**：改 `status` 的同时改 `updated`，并把文件移到对应目录——`backlog→in_progress` 移 `active/`，`→done` 移 `done/YYYY-MM/`。
   **完成判据**：卡片 `status` 与所在目录一一对应；`cancelled` 留在原目录并在 `## 阻塞项` 写取消原因。
5. **记进度**：每次推进在 `## 进度日志` 追加「日期 + 完成项 + 证据（命令/路径）」，并勾选对应 `subtasks`。
   **完成判据**：勾选数与进度日志条目数一致；每条完成项都有证据。
6. **同步看板**：`python .dsh/tools/kb.py board` 从卡片重建 `.dsh/tasks/TRACKING.md`（AUTO 区块自动，`## 备注（手工维护）` 之后的内容保留）。
   **完成判据**：命令输出任务张数与磁盘一致；表内 ID 集合 = `active/` + `backlog/` + `done/` 的卡片集合，无孤儿、无重复。
7. **归档**：项目结束或卡完成满 30 天，确认 `done/YYYY-MM/` 路径按完成月正确。
   **完成判据**：`done/` 下无跨月错放；`TRACKING.md` 已完成表的完成日与卡内 `updated` 一致。

## 质量闸门

- [ ] `status` 与目录一致（backlog/active/done 三态对齐）
- [ ] `updated` 等于本次改动日期
- [ ] `subtasks` 全部为 `[ ]` 或 `[x]`，无自由文本
- [ ] `blocked` 卡写明阻塞原因与解除条件
- [ ] `TRACKING.md` 无孤儿、无重复 ID
- [ ] 归档卡未从历史中删除（用 `cancelled` 而非删文件）
- [ ] `kb.py validate` 零 error

## 输出格式

```
任务：TASK-YYYY-MM-DD-slug（<路径>）
状态：backlog|in_progress|blocked|done|cancelled · 优先级 P0–P3
变更：<建卡 / 状态 / 子任务 / 归档>
看板：<TRACKING.md 对应行的新值>
阻塞：<原因 + 解除条件，或"无">
```

## 反面清单

- ❌ 手动 `mv` 文件却不改 `status`——目录与字段打架，看板必然失真。
- ❌ 把 `TRACKING.md` 当唯一真相——卡本体才是，看板只是投影。
- ❌ 完成就删卡——历史无法回溯；用 `done/` 归档。
- ❌ 一张卡塞多个目标——拆卡，否则完成度永远说不清。
- ❌ 建卡不写验收判据——这张卡永远无法关闭。

## 用例

**成功用例**：用户说「把知识库导出功能排进来」。`kb.py search 导出 --type task` 无命中 → `new task` 建卡 `TASK-2026-11-07-kb-export`，P2，3 条子任务；开工时移入 `active/` 并改 `in_progress`；完成后勾选、记证据、移入 `done/2026-11/`，看板三处同步。

**边界用例**：用户说「顺手记一下明天问下接口人」。无验收判据、单步、一天内完成 → 不建卡，留在当日 daily-log 的「下一步」；只有跨天未完成才升级为 `backlog` 卡。
