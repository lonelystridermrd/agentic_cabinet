---
name: agent-dispatch
description: 按 persona 卡片把任务派给隔离子 Agent（读 .dsh/agents/<name>.md → 组装受限 prompt → 启动 subagent → 记调用日志 → 回收结果）。适用"派给 X""让 code-reviewer 看看""并行审一下""隔离上下文跑"。
whenToUse: 需要独立上下文做探索/审计/对比/生成；需要只读受限权限执行；或任务可并行且互不写同一文件。
---

# agent-dispatch — 子 Agent 派发

## 触发条件

- 任务需要**独立上下文**（大段中间结果不该回灌主会话）
- 任务需要**受限权限**（只读审计、只写 `.dsh/`）
- 有 ≥2 个互不依赖的子任务可并行

**不触发**：一步就能做完的事、需要连续写同一批文件的编辑（子 Agent 会互相覆盖）。

## 卡片契约（`.dsh/agents/<name>.md`）

front-matter 字段（schema：`.dsh/schemas/agent.schema.json`）：

| 字段 | 说明 |
|---|---|
| `name` | kebab-case，与文件名一致 |
| `description` | 什么时候该用它（一句话） |
| `role` | 角色定位（一句话） |
| `domain` | `orchestration`/`coding`/`research`/`ops`/`knowledge` |
| `mode` | `read-only` 或 `read-write`（后者必须给 `can_write`） |
| `tools` | 允许使用的工具名列表（白名单；清单外的工具不得调用） |
| `can_write` | `mode: read-write` 时的路径白名单（glob） |
| `max_depth` | 允许再派子的深度，默认 0（叶子） |
| `output_contract` | 回什么、不回什么 |
| `escalate_when` | 什么情况必须停手回主会话 |

## 步骤

1. **选卡片**：`Get-ChildItem .dsh/agents/*.md`；按 `description` 匹配。没有合适卡片 → 用 `make-skill` 判定该不该新建。
   **同名路由**：本库有 4 组同名对象（`code-reviewer` / `release-manager` / `incident-responder` / `pattern-spotter`），Skill 管流程与判据、Agent 管隔离执行。回复里必须显式写「加载 Skill: X」或「派发 Agent: X」，禁止只说名字。
2. **读卡片**：读全文（front-matter + 四段正文），不要凭记忆。
3. **组装 prompt**（六段，缺一不可）：
   ```
   [角色] 你是 <name>：<role>
   [任务] <一句话目标 + 完成判据>
   [输入] <文件路径 / diff / 问题清单；只给必要上下文>
   [权限] <mode>；只可用 <tools>；<can_write 或"不得写任何文件">
   [知识库] 先读 <相关 dec-*/exp-*/sop-*>；结论要能引用 ID
   [输出] <output_contract 原文>；不要复述任务，不要贴无关日志
   ```
4. **启动**：`subagent`（独立上下文，默认）或 `subagent_fork`（需要继承本会话上下文时）。
   - `description`：3–5 个词，写清「谁在对什么做了什么」。
   - `cwd`：默认当前工作区；跨目录任务显式指定。
5. **记日志**（T06 可追溯）：
   ```
   python .dsh/tools/kb.py log-call --agent <name> --task "<一句话>" --status ok|fail|blocked
   ```
6. **回收**：子 Agent 回来先校验 `output_contract`；缺项 → 补问一次（`send_message`），仍缺则标记 `fail` 并降级为主会话自做。
7. **汇总**：给用户一张表（Agent / 任务 / 结论一句话 / 是否采纳理由），**不贴子 Agent 原文**。

## 派发前的越权检查（30 秒）

- [ ] `mode: read-only` 的卡片，prompt 里是否明确「不得写文件」**且**「不得执行写状态命令（rm / install / checkout / reset / push）」？带 `pwsh` 的只读卡尤其要写死。
- [ ] `read-write` 的 `can_write` 是否限定在 `.dsh/` 内？业务文件是否已获用户点名授权？
- [ ] 是否把秘钥/内部域名/生产数据传进了 prompt？（G5）
- [ ] 两个并行子 Agent 是否会写同一路径？（会 → 串行）
- [ ] 是否已把「允许再派子」写清（`max_depth: 0` 时明确禁止再委派）？

## 质量闸门

- [ ] 卡片存在且字段通过 `kb.py validate`
- [ ] prompt 含六段（角色/任务/输入/权限/知识库/输出）
- [ ] 调用日志已写入 `.dsh/knowledge/agent-calls/YYYY-MM-DD.jsonl`
- [ ] 结果符合 `output_contract`，或已记录一次补问
- [ ] 主会话未把子 Agent 的原始长输出整段转贴

## 输出格式

```
派发 Agent：<agent> × <n>（并行/串行）
（同名对象须标注「加载 Skill: <name>」与「派发 Agent: <name>」的区别）
| Agent | 任务 | 结论 | 采纳 |
|---|---|---|---|
| code-reviewer | 审查 X | 2 阻断 1 建议 | 采纳 2/3 |

日志：.dsh/knowledge/agent-calls/2026-11-07.jsonl
未决：<需要用户拍板的点>
```

## 反面清单

- ❌ 让子 Agent 自己决定写不写文件 —— 权限必须在 prompt 里写死。
- ❌ 把整份仓库当输入塞进去 —— 只给 diff/片段，否则上下文与成本双爆。
- ❌ 子 Agent 结论不经验证就写进知识库 —— 至少抽样复核一条。
- ❌ 并行派两个都要改同一文件的 Agent —— 后写覆盖先写。
- ❌ 忘了记日志 —— 使用效果统计（evolution-tracker）就没数据。
