---
name: pattern-spotter
description: 聚类经验与调用日志里反复出现的模式，写入 patterns/ 的好模式、反模式、复发问题清单。适用"有什么规律""老是重复""总结踩过的坑"。
whenToUse: 用户说"看看有什么规律""这类问题是不是老出现""总结下踩过的坑""沉淀成模式"；或经验条目累积到 ≥10 条、需要跨条目归纳。
---

# pattern-spotter — 模式识别

## 触发条件

- 经验条目 ≥10 条，或同类问题 30 天内出现 ≥3 次
- 需要把零散经验上升为可复用规则
- 周报/项目汇总要求「可迁移经验」

**不触发**：只有 1–2 条经验（样本不足，先积累）；单条经验的改写（直接改原条目）；纯统计数字（用 `kb.py stats`）。

## 输入

- 时间窗口（默认最近 90 天）
- 经验库：`.dsh/knowledge/experiences/<domain>/*.md`
- 调用日志：`.dsh/knowledge/agent-calls/*.jsonl`
- 现有模式：`.dsh/knowledge/patterns/*.md`

## 步骤

1. **定量摸底**：`python .dsh/tools/kb.py stats` 与 `python .dsh/tools/kb.py tags`。
   **完成判据**：记录条目总数、各 domain 数量、top 10 tag；数字来自命令输出而非估算。
2. **抽取经验要素**：逐条读 `symptom`/`root_cause`/`prevention`，每条压成一行「触发 → 根因类型 → 规则」。
   **完成判据**：窗口内每条经验都被覆盖一次，无遗漏、无重复计数。
3. **聚合调用日志**：读 `.dsh/knowledge/agent-calls/*.jsonl`，按 `agent` 与 `status` 计数。
   **完成判据**：每个 agent 的成功/失败/阻塞数可复算；失败率 >20% 的 agent 单独标出。
4. **聚类**：同根因、同 `prevention`、或同失败模式 ≥3 条 → 一个候选模式。
   **完成判据**：每个候选附 ≥3 条真实 ID 作为证据；不足 3 条的不进入下一步。
5. **命名与归档**：好模式 `pat-good-<slug>`、反模式 `pat-anti-<slug>`、复发问题 `pat-recurring-<slug>`；分别写入 `patterns/good-patterns.md`、`anti-patterns.md`、`recurring-issues.md`。
   **完成判据**：每条模式含「触发条件 / 证据 ID 列表 / 对策 / 适用边界」四要素。
6. **反查冲突**：`python .dsh/tools/kb.py search <模式关键词>` 确认不与已有 `dec-*` 冲突。
   **完成判据**：冲突项在模式里引用对应 `dec-*` 并说明取舍；无冲突则写「无」。
7. **校验与索引**：`python .dsh/tools/kb.py validate` → `python .dsh/tools/kb.py index`。
   **完成判据**：零 error；未手改任何 `index.md`。

## 质量闸门

- [ ] 每个模式 ≥3 条真实 ID 证据，且 ID 可在库中查到
- [ ] 模式不是某条经验的换标题复述
- [ ] 每条模式有可执行对策，不是「要注意」
- [ ] 三份清单各自只放对应类型，未混装
- [ ] 与已有决策的冲突已标注或已排除
- [ ] `index.md` 由脚本生成，无手工编辑
- [ ] `kb.py validate` 零 error

## 输出格式

```
窗口：<起> → <止> · 经验 <n> 条 · 调用 <m> 次
| 模式 ID | 类型 | 证据数 | 对策一句话 |
|---|---|---|---|
| pat-anti-manual-index | 反模式 | 3 | 只跑 kb.py index，不手改 |

文件：patterns/{good-patterns,anti-patterns,recurring-issues}.md
候选不足 3 条证据：<列出，留待下轮>
```

## 反面清单

- ❌ 2 条经验就抽象成模式——样本不足，规则会误导。
- ❌ 把一条经验换个标题写进 patterns/——没有跨条目归纳，不叫模式。
- ❌ 只描述现象不给对策——模式的价值在可执行。
- ❌ 手工编辑 `index.md` 或 `.index/`——违反 G6 与 AGENTS 第 8 条。
- ❌ 三份清单混装——好模式与反模式混在一起就无法当检查表用。

## 用例

**成功用例**：假设窗口内出现 3 条同根因经验（都是手工维护派生文件导致漂移）→ 聚为 `pat-anti-manual-index`，证据列 3 条真实 `exp-*`，对策「派生文件只由脚本生成」；另 3 条调用失败集中在同一 agent → 记 `pat-recurring-agent-contract`；两份清单更新后 validate 零 error。

**边界用例**：库里只有 4 条经验、无重复主题 → 判定样本不足，不写模式，输出「当前 4 条，建议 ≥10 条或同类第 3 次出现后再聚类」，避免制造伪规律。
