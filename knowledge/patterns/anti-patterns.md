# 反模式库

> 由 `pattern-spotter` 维护。每条 = 模式名 + 识别信号 + 代价 + 替代做法。只收跨 ≥2 条经验反复出现的模式。

## anti-manual-index

- **识别信号**：有人开始手工编辑 `index.md`，或索引与条目对不上。
- **代价**：索引与事实分叉，检索变成不可信，整个知识库的公信力崩塌。
- **替代**：`python .dsh/tools/kb.py index`；索引文件全部标记「自动生成，禁止手改」。
- **来源**：dec-2026-11-07-g6-index-strategy、AGENTS.md 规则 8。

## anti-skill-explosion

- **识别信号**：新 Skill 的 `whenToUse` 与已有 Skill 语义重叠 ≥50%；同一周新增 ≥3 个 Skill。
- **代价**：模型在选择上消耗注意力，触发条件互相抢，结果每个都不稳定。
- **替代**：先 `kb.py search` 查重；能改旧的就不新建；合并成带分支的单 Skill。

## anti-vague-prevention

- **识别信号**：经验条目的 `prevention` 出现「注意」「小心」「适当」。
- **代价**：不可执行 = 不可复用，等于没记录。
- **替代**：必须写成「触发条件 + 动作」，`experience-capture` 直接拒收。

## anti-over-broad-agent

- **识别信号**：一张 persona 卡片同时负责编码、调研、发布；或 `mode: read-write` 却没有 `can_write` 白名单。
- **代价**：子 Agent 越权写，主会话无法回收结果，权限边界失控。
- **替代**：一卡一职责；写权限必须给 glob 白名单，且限定 `.dsh/` 内。
