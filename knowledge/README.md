# 知识库使用说明

这是个人认知操作系统的**长期记忆**。四类资产 + 两份过程日志，全部由 front-matter 驱动、由脚本索引。

## 放什么 / 不放什么

| 目录 | 放什么 | 不放什么 | 写入方 |
|---|---|---|---|
| `decisions/` | 一条决策 = 场景 + 备选 + 理由 + 后果 + 置信度 | 讨论过程、会议纪要 | `decision-logger` |
| `experiences/<domain>/` | 症状 → 根因 → 修法 → **一句 prevention** | 流水账、情绪、原始对话 | `experience-capture` |
| `sops/<domain>/` | 可重复执行的步骤 + 检查点 + 版本 | 一次性操作、个人偏好 | `sop-executor` / `make-skill` |
| `patterns/` | 跨条目归纳出的好模式 / 反模式 / 复发问题 | 单条经验的重复 | `pattern-spotter` |
| `daily-logs/` | 当天做了什么、下一步、卡点 | 长篇复盘 | `bootstrap` |
| `agent-calls/` | 子 Agent 派发的机器可读日志（jsonl） | 子 Agent 的完整输出 | `agent-dispatch` |
| `.index/` | 脚本生成的索引产物 | 任何手工内容 | `kb.py index` |

## 三个铁律

1. **单条记录 ≤5 分钟**：超时说明信息太大，拆成多条或只留结论。
2. **没有 prevention / rationale 的条目不收**：`kb.py validate` 会拦，`experience-capture` 也会拦。
3. **只存结论 + 上下文**：原文对话、整段公司代码不入库（G5）。

## 常用命令

```powershell
# 检索（同时命中决策 / 经验 / SOP）
python .dsh/tools/kb.py search 认证
python .dsh/tools/kb.py search typescript --type experience --tag generics

# 新建（模板 + 正确路径 + 正确 ID）
python .dsh/tools/kb.py new decision --title "索引方案选型" --slug index-strategy
python .dsh/tools/kb.py new experience --title "GBK 编码炸 py" --slug gbk-console --domain debugging
python .dsh/tools/kb.py new sop --title "feature dev" --slug feature-development --domain coding

# 维护
python .dsh/tools/kb.py index      # 重建索引
python .dsh/tools/kb.py validate   # schema + 命名 + Skill/Agent 一致性
python .dsh/tools/kb.py tags       # tag 词表（写新条目前先查，避免同义词）
python .dsh/tools/kb.py stats
```

## 检索入口（T07 验收）

四种入口：`tag`（`--tag`）、`domain`（`--domain`）、日期（`--since`）、全文（关键词参数）。
索引为纯文件扫描 + 派生 JSON（G6），条目 <200 时不做向量检索；条目过 200 或漏召回 >20% 再升级。
