---
id: dec-2026-11-14-embedded-c-skill-split
date: 2026-11-14
context: 需要把个人嵌入式 C 开发经验固化成可被 Harness 自动遵循的 Skill 体系
decision: 拆成三个 Skill（c-embedded-coding 规范执行、c-embedded-playbook 设计手法、experience-interview 引导式梳理）加一份共享 profile，经验按「可执行规则进 Skill、单条踩坑进 exp-*、取舍进 dec-*」分流
alternatives:
  - 单个大 Skill 覆盖编码/设计/梳理
  - 只做 Bug 分析类 Skill 试点
  - 规则全塞进 AGENTS.md 常驻指令
rationale: 编码规范与设计手法触发场景不同（写代码 vs 做设计），混在一个 Skill 里会导致每次写函数都加载整套设计文档；profile 单独一份使参数只改一处；梳理流程独立成 Skill 才能重复执行而不污染前两者
consequences:
  - 三个 Skill 的 whenToUse 需要持续校准，防止职责漂移
  - 规范条目与 exp-* 条目可能重复，需以「Skill 留一行 + 指向 exp ID」约束
  - profile 成为单点，改错会影响全部三个 Skill
confidence: medium
tags:
  - skill
  - domain
  - c
  - embedded
  - governance
status: accepted
---

# 嵌入式 C 领域 Skill 的拆分与知识去向

## 背景

用户是嵌入式 C / 网络数通方向工程师，希望 Harness 后续开发**完全按他的经验操作**，而不是每次即兴发挥通用写法。现有 `.dsh/skills/` 里 20+ 个 Skill 全是流程型（bootstrap、review、release、incident），没有领域型 Skill；`kb.py search 嵌入式` 零命中，不存在重复实现。

关键难点不是"写几条规范"，而是：① 规范与设计手法触发场景不同；② 用户的隐性经验需要被**问出来**；③ 哪些进 Skill、哪些进知识库必须有个稳定判据，否则两处漂移。

## 评估

| 方案 | 触发粒度 | 维护成本 | 失败代价 |
|------|---------|---------|---------|
| A 单个大 Skill | 粗（写代码/做设计都加载） | 低 | 正文逼近 8192 字节上限，设计文档挤掉编码规则 |
| B 只做 Bug 分析试点 | 窄 | 低 | 覆盖不到日常编码，用户诉求（编码规范）没解决 |
| C 三个分工 Skill + 共享 profile | 细 | 中（需校准 whenToUse） | 职责漂移；profile 单点 |
| D 全塞 AGENTS.md | 常驻 | 低 | 违反 12 条上限，违反"超 1 句即下沉"判据 |

## 最终选择

选 C。三个 Skill 按**动作**切分，而不是按知识主题切分：

- `c-embedded-coding`：动作为「写/改/审代码」，装载规范 + 安全规则 + 陷阱清单。
- `c-embedded-playbook`：动作为「做设计/选型」，装载 socket、内存与数据结构、性能、时空取舍、并发。
- `experience-interview`：动作为「梳理经验」，产出回写到前两者的 references 与知识库。

共享 `references/profile.md` 存放可调参数（缩进、行宽、错误码、日志宏、编译开关）。经验去向判据：

| 结论形态 | 容器 |
|---|---|
| 每次都要遵守的可执行规则 | Skill references（style/safety） |
| 多方案取舍手法 | Skill references（playbook） |
| 具体踩坑事件 | `exp-*` |
| 一次性技术取舍 | `dec-*` |
| 默认数字/开关 | `profile.md` |

## 后果与代价

- 三个 whenToUse 需要持续校准；出现"该触发没触发"时优先改描述而不是加 Skill。
- 规范与 exp-* 会重复：约定 Skill 只留一行规则 + 指向 exp ID，详细因果留在 exp。
- profile 是单点，改错会同时影响三个 Skill；因此 profile 变更有强制记录（变更记录表）。
- 初次内容为「骨架 + 通识」，未标注 `我踩过` 的条目需用户逐条确认后才算个人经验。

## 置信度理由

medium：拆分依据是触发场景差异（可验证），但三条 Skill 的边界是否会被真实使用验证，要等首次真实任务跑过才知道（对应 `TASK-2026-11-07-p1-domain-skills` 的验证目标）。
