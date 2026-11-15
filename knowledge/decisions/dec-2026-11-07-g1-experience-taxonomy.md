---
id: dec-2026-11-07-g1-experience-taxonomy
date: 2026-11-07
context: "经验库按「领域」还是「问题类型」分类"
decision: "领域为主分类目录 + 问题类型为副字段，两者都进索引"
alternatives: ["只按领域分类", "只按问题类型分类", "两层标签：领域(主) + 问题类型(副)"]
rationale: "分类维度即检索维度。领域贴近「我现在在做哪类活」，问题类型贴近「我在复用什么」，两者是不同检索意图，缺一都会让另一半条目找不到；目录按领域分便于人眼浏览，副字段补足复用视角，成本只多一个 front-matter 字段。"
consequences: ["每条经验多维护一个 problem_type 字段", "索引必须同时按 domain 和 problem_type 建入口", "未来若问题类型膨胀需先收敛枚举"]
confidence: high
tags: [knowledge, taxonomy, indexing]
status: proposed
---

# 经验库分类维度

## 背景

T01 建目录时必须先定分类维度。定错后迁移要改所有条目的 front-matter、目录位置与索引，成本随条目数线性上升。这是闸门题 G1，D1 开工前必须定。

## 评估

| 方案 | 人眼浏览 | 复用检索 | 迁移成本 | 结论 |
|---|---|---|---|---|
| 只按领域 | 好 | 差（想查「所有性能坑」要全库扫） | 低 | ❌ |
| 只按问题类型 | 差（coding 的坑散落各类型） | 好 | 低 | ❌ |
| 领域(主) + 问题类型(副) | 好 | 好 | 一次到位 | ✅ |

## 最终选择

目录按 `domain` 分：`experiences/{coding,debugging,architecture,process}/`；front-matter 同时带 `domain`（枚举）与 `problem_type`（枚举 `bug|performance|tooling|process|knowledge`）。
`kb.py` 的索引与检索对两者都建入口（`--domain` / `--tag` / 全文）。放弃了「单一维度带来的极简」，换来两个检索视角。

## 后果与代价

- 新增条目时必须判断 problem_type，多花约 10 秒；
- `problem_type` 枚举需收敛，否则会退化成自由文本。

## 置信度理由

高：维度选择是可逆的软决策，且实践上两个检索视角都被验证有用；即便日后合并维度，迁移脚本可由索引自动重写。

## 待确认

用户如倾向单维度，只需删除 `problem_type` 字段并重跑 `kb.py index`，目录结构不变。
