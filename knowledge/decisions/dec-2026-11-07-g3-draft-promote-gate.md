---
id: dec-2026-11-07-g3-draft-promote-gate
date: 2026-11-07
context: "元 Skill(make-skill) 产出的 SKILL.md 草稿自动入库还是人工确认后入库"
decision: "草稿一律落在 .dsh/drafts/skills/，人工确认后由 kb.py promote 迁入 .dsh/skills/，确认动作 ≤1 分钟"
alternatives: ["自动入库", "沙箱草稿 + 人工确认 + 脚本迁移", "只生成不落盘"]
rationale: "自动入库会随使用量线性堆积重叠 Skill，清理成本远高于确认成本；只生成不落盘则丢失草稿。沙箱 + 一条命令迁移把「治理成本」压到一次 yes/no，同时保留可审计的草稿历史。"
consequences: ["每日多一次确认动作(约 1 分钟)", "需要维护 drafts 目录的清理规则", "禁止把 drafts 目录纳入 DSH 自动装载路径"]
confidence: high
tags: [process, skill, governance]
status: proposed
---

# 元 Skill 草稿入库闸门

## 背景

make-skill 会批量产出 SKILL.md。若直接写进 `.dsh/skills/`，DSH 会立即装载——命名冲突、触发条件重叠、权限描述不全的草稿会直接污染会话目录，且模型无法区分「正式」与「草稿」。

## 评估

| 方案 | 库干净度 | 摩擦 | 可追溯 | 结论 |
|---|---|---|---|---|
| 自动入库 | 低（重叠堆积） | 无 | 差 | ❌ |
| 沙箱草稿 + 人工确认 | 高 | 1 次确认 | 好 | ✅ |
| 只生成不落盘 | 高 | 0 | 无 | ❌ |

## 最终选择

`make-skill` 只写 `.dsh/drafts/skills/<name>/SKILL.md`（该目录**不在** DSH 装载根内，因此不会被自动发现）。
用户确认后执行 `python .dsh/tools/kb.py promote .dsh/drafts/skills/<name>`：校验 name/description/whenToUse 后才复制到 `.dsh/skills/`，目标已存在则拒绝覆盖。

## 后果与代价

- 舍弃「生成即生效」的速度；
- drafts 会积累，需要 `make-skill` 每次提示「当前有 N 份未确认草稿」；
- promote 只复制不删除，确认后需手动清理草稿。

## 置信度理由

高：DSH 的装载行为已实测（扫描 `.dsh/skills` 顶层目录），把草稿放在装载根之外即可获得确定性隔离，不依赖模型自律。
