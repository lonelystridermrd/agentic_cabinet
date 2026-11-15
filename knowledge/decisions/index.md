<!-- 由 .dsh/tools/kb.py index 自动生成，禁止手改；改条目后重跑 kb.py index -->

# 决策索引

共 12 条 · 生成于 2026-11-16 00:05 · 检索 `python .dsh/tools/kb.py search <关键词>`

## 按 tag

- **agents-md**（1）：`dec-2026-11-07-g2-agents-md-limit`
- **c**（1）：`dec-2026-11-14-embedded-c-skill-split`
- **compliance**（1）：`dec-2026-11-07-g5-code-snippet-policy`
- **decision**（3）：`dec-2026-11-15-iomux-design-choice`、`dec-2026-11-15-decision-layer-skill`、`dec-2026-11-07-g4-confidence-scale`
- **deployment**（1）：`dec-2026-11-07-g8-install-strategy`
- **design**（1）：`dec-2026-11-15-iomux-design-choice`
- **domain**（1）：`dec-2026-11-14-embedded-c-skill-split`
- **dsh**（1）：`dec-2026-11-07-g8-install-strategy`
- **embedded**（1）：`dec-2026-11-14-embedded-c-skill-split`
- **epoll**（1）：`dec-2026-11-15-iomux-design-choice`
- **evaluation**（1）：`dec-2026-11-14-research-layers-separation`
- **evidence**（1）：`dec-2026-11-14-research-layers-separation`
- **governance**（3）：`dec-2026-11-15-decision-layer-skill`、`dec-2026-11-14-embedded-c-skill-split`、`dec-2026-11-07-g3-draft-promote-gate`
- **indexing**（2）：`dec-2026-11-07-g6-index-strategy`、`dec-2026-11-07-g1-experience-taxonomy`
- **iomux**（1）：`dec-2026-11-15-iomux-design-choice`
- **knowledge**（3）：`dec-2026-11-07-g5-code-snippet-policy`、`dec-2026-11-07-g4-confidence-scale`、`dec-2026-11-07-g1-experience-taxonomy`
- **performance**（1）：`dec-2026-11-07-g6-index-strategy`
- **presets**（1）：`dec-2026-11-07-g8-install-strategy`
- **process**（3）：`dec-2026-11-07-g7-drill-task-scope`、`dec-2026-11-07-g3-draft-promote-gate`、`dec-2026-11-07-g2-agents-md-limit`
- **research**（2）：`dec-2026-11-15-decision-layer-skill`、`dec-2026-11-14-research-layers-separation`
- **schema**（1）：`dec-2026-11-07-g4-confidence-scale`
- **security**（1）：`dec-2026-11-07-g5-code-snippet-policy`
- **skill**（4）：`dec-2026-11-15-decision-layer-skill`、`dec-2026-11-14-research-layers-separation`、`dec-2026-11-14-embedded-c-skill-split`、`dec-2026-11-07-g3-draft-promote-gate`
- **skills**（1）：`dec-2026-11-07-g8-install-strategy`
- **taxonomy**（1）：`dec-2026-11-07-g1-experience-taxonomy`
- **tooling**（1）：`dec-2026-11-07-g6-index-strategy`
- **validation**（1）：`dec-2026-11-07-g7-drill-task-scope`

## 全部（按日期倒序）

| ID | 日期 | 标题 | 状态 | 置信度 | tags |
|---|---|---|---|---|---|
| [dec-2026-11-15-iomux-design-choice](dec-2026-11-15-iomux-design-choice.md) | 2026-11-15 | 自研 libiomux：epoll 水平触发 + EPOLLONESHOT 抑制 + 单 Reactor + 可配置 w | accepted | medium | design, iomux, epoll, decision |
| [dec-2026-11-15-decision-layer-skill](dec-2026-11-15-decision-layer-skill.md) | 2026-11-15 | 新增 tech-selection-decision 承担决策建议：审来源、重建四场景、七维评估、单点发散、冲突裁决后给 | accepted | medium | skill, decision, research, governance |
| [dec-2026-11-14-research-layers-separation](dec-2026-11-14-research-layers-separation.md) | 2026-11-14 | 取证层保持不变；新增 tech-evaluation 作为编排层，负责广度发散、按约束收敛、原理与演进分析、编译产物实测 | accepted | medium | research, skill, evaluation, evidence |
| [dec-2026-11-14-embedded-c-skill-split](dec-2026-11-14-embedded-c-skill-split.md) | 2026-11-14 | 拆成三个 Skill（c-embedded-coding 规范执行、c-embedded-playbook 设计手法、e | accepted | medium | skill, domain, c, embedded, governance |
| [dec-2026-11-07-g8-install-strategy](dec-2026-11-07-g8-install-strategy.md) | 2026-11-07 | Skill 复制到用户级 skill 根（%DSH_HOME%/skills）；子 Agent 声明为 @deepsee | proposed | medium | deployment, dsh, presets, skills |
| [dec-2026-11-07-g7-drill-task-scope](dec-2026-11-07-g7-drill-task-scope.md) | 2026-11-07 | 用当前真实在建任务(认知操作系统自身落地)做演练，低风险、可回退、不碰生产数据与对外接口 | proposed | medium | process, validation |
| [dec-2026-11-07-g6-index-strategy](dec-2026-11-07-g6-index-strategy.md) | 2026-11-07 | 本周做纯文件扫描 + 三维 tag 索引（kb.py）；条目 >200 或漏召回 >20% 再上向量检索 | proposed | high | indexing, tooling, performance |
| [dec-2026-11-07-g5-code-snippet-policy](dec-2026-11-07-g5-code-snippet-policy.md) | 2026-11-07 | 默认不存原文；只存「文件类型 + 关键签名 + 复现步骤」，确需片段则脱敏且只留本地、不入库 | proposed | high | compliance, knowledge, security |
| [dec-2026-11-07-g4-confidence-scale](dec-2026-11-07-g4-confidence-scale.md) | 2026-11-07 | 三档枚举 high\|medium\|low，附一句理由；条目 ≥30 条后再评估是否升级为数值 | proposed | medium | knowledge, schema, decision |
| [dec-2026-11-07-g3-draft-promote-gate](dec-2026-11-07-g3-draft-promote-gate.md) | 2026-11-07 | 草稿一律落在 .dsh/drafts/skills/，人工确认后由 kb.py promote 迁入 .dsh/skil | proposed | high | process, skill, governance |
| [dec-2026-11-07-g2-agents-md-limit](dec-2026-11-07-g2-agents-md-limit.md) | 2026-11-07 | 上限 12 条，超出强制下沉 Skill；两周后按实际违反率增删 | proposed | medium | process, agents-md |
| [dec-2026-11-07-g1-experience-taxonomy](dec-2026-11-07-g1-experience-taxonomy.md) | 2026-11-07 | 领域为主分类目录 + 问题类型为副字段，两者都进索引 | proposed | high | knowledge, taxonomy, indexing |
