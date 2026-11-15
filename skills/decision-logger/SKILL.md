---
name: decision-logger
description: 把一次技术选型/架构取舍/流程变更沉淀成结构化决策条目（dec-*），写 front-matter、对比矩阵、后果与置信度，并刷新索引。适用"选型""对比""定方案""要不要换""为什么当初这么定"。
whenToUse: 用户提出选型、方案取舍、架构或流程变更；或一次对话里出现"两种做法都行"的分叉；或事后需要回查"为什么当初这么选"。
---

# decision-logger — 决策记录

## 触发条件

满足任一即执行：出现 A/B 方案分叉、要拍板不可逆选择、要改已生效的约定、或用户问「当初为什么这么选」。
**不触发**：纯事实查询、纯执行（没有备选）、个人偏好且无后果。

## 输入

- 场景一句话（为什么现在必须定）
- 候选方案 ≥2（少于 2 个说明还没想清，先补）
- 评估维度（由用户确认，默认：成本 / 复杂度 / 可回退性 / 与已有决策冲突）
- 约束（时间、人力、合规、现有技术栈）

## 步骤

1. **查重**：`python .dsh/tools/kb.py search <关键词> --type decision`。命中同主题：
   - 结论仍成立 → 在旧条目追加 `## 复议记录`，不新建；
   - 结论被推翻 → 新建条目并在 front-matter 写 `supersedes: <旧ID>`，旧条目改 `status: superseded`。
2. **建骨架**：`python .dsh/tools/kb.py new decision --title "<场景>" --slug <kebab-case>`。
3. **填 front-matter**（字段顺序固定，见 `.dsh/schemas/decision.schema.json`）：
   `id` `date` `context` `decision` `alternatives` `rationale` `consequences` `confidence` `tags` `status`
   - `rationale` 必须写「为什么不是别的」，只写优点不合格；
   - `consequences` 至少 1 条代价，只有好处的决策通常是没想清；
   - `confidence` 三档（G4）：`high` 有实测/先例支撑，`medium` 有推理无实测，`low` 靠直觉且缺数据——`low` 必须在正文写「什么新信息会推翻它」。
4. **写正文三段**：`## 背景`、`## 评估`（对比矩阵，维度来自输入）、`## 最终选择`（含「放弃了什么」）。
5. **校验 + 入索引**：`python .dsh/tools/kb.py validate` → `python .dsh/tools/kb.py index`。
6. **回执**：给出条目路径、ID、一句话结论、以及需要用户确认的点（若 status 仍为 `proposed`）。

## 对比矩阵写法

| 方案 | 成本 | 复杂度 | 可回退性 | 与已有决策冲突 | 结论 |
|---|---|---|---|---|---|
| A | 低 | 低 | 高 | 无 | ✅ |
| B | 中 | 中 | 低 | 与 dec-xxx 冲突 | ❌ |

矩阵只放**能判定的**维度；写「好/不好」的维度删掉，换可量化的（工期、文件数、依赖数、回滚步骤数）。

## 质量闸门（不合格就退回，不入库）

- [ ] `alternatives` ≥2，且每条都写过为什么不选
- [ ] `rationale` 能反查到具体约束，不是"因为更好"
- [ ] `consequences` 至少含 1 条代价
- [ ] `confidence` 与正文「置信度理由」一致
- [ ] 没有与旧决策冲突却未标注 `supersedes`
- [ ] `kb.py validate` 零 error

## 输出格式

```
决策已落库：<相对路径>
ID：dec-YYYY-MM-DD-slug · status: proposed|accepted · confidence: high|medium|low
结论：<一句话>
待确认：<需要用户拍板的点，或"无">
```

## 反面清单

- ❌ 事后补写却写成「当初就这么想的」——如实写 `confidence: low` 并注明是回溯。
- ❌ 把讨论过程、聊天记录贴进正文——只留结论 + 上下文。
- ❌ 一个决策写三个主题——拆成多条，各自独立可检索。
- ❌ 只写「选了 A」不写「为什么不是 B」——三个月后无法复用。
