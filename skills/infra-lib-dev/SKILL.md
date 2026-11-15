---
name: infra-lib-dev
description: 基础设施库开发的全流程编排：需求→调研→决策→开发→评审→测例→执行，每阶段用脚本校验产物，未通过不得进入下一阶段。适用"从头做一个库""按流程开发""端到端交付"。
whenToUse: 用户要求开发一个基础库/组件/模块并端到端交付；或要求"按流程走一遍""从需求到测试"；或需要把调研、决策、编码、评审、测试串成一次连续作业。
---

# infra-lib-dev — 基础设施库开发编排

> 本 Skill 是**唯一的入口**。它不替代各阶段技能，而是负责：顺序、产物、校验、拒绝跳步。
> 硬闸门是脚本，不是这段话：`python .dsh/tools/pipeline_gate.py --task <id> --phase <name>` 返回非 0 即停机。

## 触发条件

- 从零开发一个库/组件，且用户要求端到端（含调研/决策/测试）
- 用户说"按流程来""完整走一遍""从需求做到测试"
- **不触发**：单文件小改（用 `c-embedded-coding`）；只调研（`tech-evaluation`）；只评审（`code-reviewer`）

## 输入（缺一项就先问）

1. 任务 id（用于 `.dsh/runs/<id>/`，kebab-case）
2. 目标与验收标准（可量化）
3. 约束：平台、内核、内存、体积、交付期
4. 是否允许派子代理（评审/测例阶段用）

## 状态文件

```
.dsh/runs/<task>/
├── run.json          # 阶段状态、产物路径、校验时间（由 gate 写入）
├── spec.md           # 阶段 1
├── reports/*.md      # 阶段 2
├── decisions/*.md    # 阶段 3（或引用 .dsh/knowledge/decisions/dec-*.md）
├── review.md         # 阶段 5
├── test-plan.md      # 阶段 6
├── test.log          # 阶段 7
└── style/*.log       # 阶段 4 每文件 style_check 输出
```

## 七阶段

| # | 阶段 | 调用 | 产物 | 闸门 |
|---|---|---|---|---|
| 1 | 需求 | `spec-writer` | `spec.md` | 含"验收标准"且 ≥1 条可量化 |
| 2 | 调研 | `tech-evaluation`（取证可派 `tech-investigator`） | `reports/<slug>.md` | 候选 ≥8、含证据表、标明未实测项 |
| 3 | 决策 | `tech-selection-decision` + `decision-logger` | `dec-*.md` | `status: accepted`，含反转条件与代价 |
| 4 | 开发 | `c-embedded-coding`（L0→L1） | 代码 + `style/*.log` | **改动文件集合 == style 通过文件集合** |
| 5 | 评审 | `code-reviewer`（建议派子代理）+ `c-embedded-coding` 30 项 | `review.md` | 含 P0–P3 分级，且 30 项清单与注释审计均通过 |
| 6 | 测例 | 派子代理产出 | `test-plan.md` | 每条验收标准至少 1 个用例，含判定方式 |
| 7 | 执行 | 命令 | `test.log` | 测试退出码 0，日志含通过数 |

## 每阶段固定动作（不许省）

1. 加载对应技能（`skill` 工具，名字写进 `run.json`）。
2. 执行技能步骤，产出文件。
3. 跑闸门：`python .dsh/tools/pipeline_gate.py --task <id> --phase <name>`。
4. 闸门失败 → 修到通过，**不得进入下一阶段**；把失败原因写进 `run.json`。
5. 每阶段结束输出「阶段卡」：阶段、调用的技能、产物路径、闸门输出摘要。

## 阶段 4 的额外硬约束

- 每写完**一个** `.c`/`.h`，立刻跑：
  `python .dsh/tools/style_check.py <file>`，输出存 `style/<file>.log`。
- 全部写完后跑 `python .dsh/tools/style_check.py --all <dir>` 复核。
- 跑 `python .dsh/tools/comment_audit.py <src/*.c>`，输出存 `comments.log`，必须 `0 missing`。
- 任何文件 FAIL 或存在未注释函数 → 不得进入阶段 5。
- 首次生成遵守 `c-embedded-coding/references/first-pass.md` 的 13 条硬禁止；
  迭代修改遵守 `references/iteration.md` 的 diff 范围检查。

## 质量闸门（本 Skill 自身）

- [ ] `.dsh/runs/<task>/run.json` 存在，七阶段都有记录
- [ ] 每次阶段推进都有 gate 的 PASS 输出（时间戳晚于阶段开始）
- [ ] 闸门失败记录保留，未被覆盖
- [ ] 阶段 4 的"改动文件集合 == style 通过集合"
- [ ] 最终 `/test.log` 退出码 0

## 输出格式（每阶段）

```
阶段：<n> <name> ｜ 技能：<skill>
产物：<路径>
闸门：PASS/FAIL —— <gate 摘要>
下一阶段：<name> / 停止（原因）
```

## 反面清单

- ❌ 跳过阶段 2/3 直接写代码——没有决策就没有"为什么这么写"
- ❌ 闸门失败后"先往下走，回头补"——回头不会补
- ❌ 只对部分文件跑 style_check——gate 会比对集合，差一个就 FAIL
- ❌ 用"我已经检查过了"代替 gate 输出——只认脚本退出码
- ❌ 把所有阶段塞进一条回复，不落文件——没有产物就无法校验

## 用例

**成功用例**：用户要做一个嵌入式事件分发库。→ 建 `.dsh/runs/iomux/`；阶段 1 出 `spec.md`；阶段 2 出调研报告；阶段 3 出 `dec-*`（accepted）；阶段 4 逐文件 style_check；阶段 5 派 `code-reviewer` 出 `review.md`；阶段 6 出 `test-plan.md`；阶段 7 `make check` 出 `test.log`；每步 gate PASS 才前进。

**边界用例**：用户说"帮我改个拼写错误"。→ 不触发本 Skill，直接 `c-embedded-coding` 的轻量路径。
