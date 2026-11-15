---
id: dec-2026-11-07-g8-install-strategy
date: 2026-11-07
context: "把工作区的 Skill 与子 Agent 安装进 DeepSeek Harness 的方式与落点"
decision: "Skill 复制到用户级 skill 根（%DSH_HOME%/skills）；子 Agent 声明为 @deepseek-ai/dsh-agent-preset 追加到 profile 的 cordis.patch.yml"
alternatives: ["只留在项目级 .dsh（不安装）", "Skill 用户级 + Agent 用 profile 补丁声明 preset", "两者都做成 bundle 用 plugin_manager 安装"]
rationale: "Skill 的用户级根是被监视的目录，复制即生效、免重启，成本最低；子 Agent 在 DSH 中只能由 preset 插件树声明（不扫描目录），而安装 bundle 需要 plugin_manager 或手工 pnpm，当前会话没有该工具，profile 补丁是唯一无需装包的合法入口。两者都在工作区留有源文件与再生成命令，可随时重装或回滚。"
consequences: ["profile 补丁可能被 Web 设置重写，需要 check-install 发现并重跑 apply-presets", "改 agent 卡片后必须重新导出并重启才生效", "只读 agent 的只读性仍靠 persona 约束，工具层无法强制", "模型自动选 preset 需要 allowedAgentPresets，未启用"]
confidence: medium
tags: [deployment, dsh, presets, skills]
status: proposed
---

# 安装策略：Skill 用户级 + Agent preset

## 背景

阶段 0 的产物都在工作区 `.dsh/` 内。工作区级 Skill 只对当前项目根生效，子 Agent 则完全不是 DSH 的原生概念（DSH 的 Skill 发现根只包含 `.dsh/skills` 与 `~/.dsh/skills`，agent 由 preset 插件树声明）。要「安装进 DSH」，必须分别选择落点。

## 评估

| 方案 | 生效范围 | 摩擦 | 可回滚 | 结论 |
|---|---|---|---|---|
| 只留项目级 | 单工作区 | 零 | 天然 | ❌ 不算安装 |
| Skill 用户级 + Agent 用 profile 补丁 | 全局 | 需重启一次 | 备份 + 一键移除 | ✅ |
| 全部做成 bundle | 全局 | 需 plugin_manager/pnpm，当前不可用 | 卸载包 | ⏸ 后续可选 |

## 最终选择

- **Skill** → `python .dsh/tools/kb.py install --scope user`，复制到 `%DSH_HOME%/skills`，watcher 自动发现，免重启。
- **Agent** → `export-presets` 从卡片生成 `@deepseek-ai/dsh-agent-preset` 声明，`apply-presets` 带备份追加进 profile 补丁，重启后进入 agent 列表。
- **校验** → `check-install` 同时核对 Skill 齐全/preset 区块存在；`yamlish.py` 在写入前解析合并结果，解析失败即中止且不改 profile。

## 后果与代价

- 每次改 agent 卡片要重新导出 + 重启；
- profile 补丁若被 Web 设置重写，preset 会消失（`check-install` 可发现，重跑一条命令恢复）；
- 只读 agent 仍是「提示词约束」，不是内核强制；
- 模型自动按名选 preset 未启用（需 `allowedAgentPresets`，会要求覆写内置 preset 的完整插件列表，升级易碎）。

## 置信度理由

中：Skill 用户级装载路径已由 DSH 源码确认（rank 400 的 `<dshHome>/skills`）；preset 声明的插件名全部取自内置 preset 的实际 YAML，写法对齐官方 `review` 示例，但**尚未重启验证激活**——这是本决策唯一未闭环的验证项，重启后应立即跑 `check-install` 并在 UI 确认 `pcos · <name>` 出现在 agent 列表。
