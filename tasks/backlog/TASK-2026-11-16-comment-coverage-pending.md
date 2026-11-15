---
id: TASK-2026-11-16-comment-coverage-pending
title: 注释覆盖与流水线遗留事务
status: in_progress
priority: P1
created: 2026-11-16
updated: 2026-11-16
domain: coding/general
related_decisions: []
related_experiences: []
subtasks:
  - "[x] 注释规范升级：每个函数头（含 static）+ 关键流程注释"
  - "[x] comment_audit 纳入 gate，设覆盖率阈值"
  - "[ ] review 阶段强制跑 c-embedded-coding 30 项 + 注释审计"
  - "[ ] iomux_v2 P2 三项"
  - "[ ] run.json task 名修正"
  - "[ ] 技能调用溯源（插件日志）"
  - "[ ] iomux（v1）在 gcc 15 下编译失败（线程名 16 字节、write 返回值）"
---

# 注释覆盖与流水线遗留事务

## 目标

把「函数头注释 + 关键流程注释」从"个人习惯"变成规范、工具、闸门三层约束，并清掉 iomux_v2 的遗留项。

## 非目标

- 不重写 iomux_v2 的业务逻辑
- 不为注释调整对外接口

## 待定事务

### A. 注释规范（c-embedded-coding）

- 现状：S8 只要求「公共接口」写契约，实现注释仅限三类场合；**未要求每个函数头注释**。
- 待定：是否升级为「每个函数定义（含 static）必须有头注释：做什么 / 参数 / 返回 / 上下文」，并新增「关键流程注释：状态迁移、不变量、顺序约束」。
- 影响面：S8、first-pass.md（L0）、review-checklist 第 1 项、style_check。

### B. 工具

- `comment_audit.py` 已建：按函数定义检测前一行是否为块注释。
- 待定：阈值（建议 100% 函数头；测试文件可豁免）、是否把「关键流程」做成可检查的启发式（如 switch/锁/goto 前必须有注释）。
- 待定：把它接入 `pipeline_gate --phase development`，与 style 覆盖率并列。

### C. 流程

- 现状：阶段 5 用 `code-reviewer`（通用 P0–P3），没有跑 `c-embedded-coding` 的 30 项清单，注释覆盖无人检查。
- 待定：review 阶段固定两步——通用 P0–P3 + `c-embedded-coding` 清单（含注释审计），两者都过才 PASS。

### D. iomux_v2 遗留

- P2-1：`drain_completions` 每轮扫所有 worker 完成环（空环也有开销）。
- P2-2：`completion_push` 满时 `sched_yield` 自旋，需退避/超时。
- P2-3：`stats` 非原子读取（文档已标注，可改 `_Atomic`）。
- `run.json` 的 `task` 字段是 `devlog`，应为 `iomux-v2`。
- 技能调用溯源：`--skill` 仍是自报，未接插件日志。

## 进度日志

### 2026-11-16

- 建卡。审计结果：`iomux_v2/src` 67 个函数定义，仅 4 个有头注释（6%）。
- 根因确认：规范只约束公共接口；L0 与 review 都未覆盖函数级注释。
- 已完成：S8 增加「全部函数头注释」硬性条款；first-pass 扩到 13 条；review-checklist 第 1 项改写；`comment_audit.py` 接入 `pipeline_gate` 的 development 阶段；`infra-lib-dev` 阶段 5 要求追加 30 项清单。
- 已验证：v2 注释 67/67、v1 63/63；v2 `make check` 全过；development/execution 闸门 PASS。
- 遗留：v1 在 gcc 15 下因线程名缓冲区与 `write` 返回值告警编译失败（既有缺陷，未修）。

## 阻塞项

- 无

## 下一步

- 确认 A 的规则粒度（是否含 static、是否要求关键流程注释），再改规范与工具。
