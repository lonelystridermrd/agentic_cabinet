# 安装到 DeepSeek Harness

> 一句话：Skill 装到 **用户级 skill 根**（所有工作区可用，免重启）；子 Agent 装成 **DSH agent preset**（重启后出现在 agent 列表）。
> 本目录的产物由 `kb.py` 生成，不要手改；改源文件后重跑对应命令。

## 已安装内容

| 类型 | 装到哪 | 数量 | 生效条件 |
|---|---|---|---|
| Skill | `%DSH_HOME%\skills\<name>\SKILL.md`（默认 `C:\Users\<user>\.dsh\skills`） | 15 | **免重启**，DSH 监视该目录 |
| 子 Agent | `%DSH_HOME%\profiles\<profile>\cordis.patch.yml` 末尾的 `pcos presets` 区块 | 17 | **需重启 DSH** |

来源：工作区 `.dsh/skills/` 与 `.dsh/agents/`（工作区是源，用户级是安装副本）。

## 命令

```powershell
$py = "C:\Users\77214\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$env:PYTHONUTF8 = "1"

# 1. 安装 Skill 到用户级（--dry-run 先看清单）
& $py .dsh/tools/kb.py install --scope user --dry-run
& $py .dsh/tools/kb.py install --scope user

# 2. 从 agents/*.md 生成 preset 补丁（只解析不写 profile）
& $py .dsh/tools/kb.py export-presets

# 3. 应用到 profile（自动备份 + 合并后 YAML 校验，重启生效）
& $py .dsh/tools/kb.py apply-presets

# 4. 核对安装状态（Skill 齐全 + preset 区块在）
& $py .dsh/tools/kb.py check-install

# 回滚 preset（Skill 回滚 = 删目标目录下对应子目录）
& $py .dsh/tools/kb.py remove-presets
```

## 生成物

| 文件 | 用途 |
|---|---|
| `dsh-agent-presets.patch.yml` | 17 个 `@deepseek-ai/dsh-agent-preset` 声明，可由 `kb.py export-presets` 重新生成 |
| `manifest-skills.json` | 上次 Skill 安装的时间、目标目录、清单 |
| `backup/cordis.patch.yml.*.bak` | 每次 `apply-presets` 前的 profile 补丁备份（回滚用） |

## preset 组成（每个 agent）

```
persona（角色 + 只读/写权限边界 + 停手条件 + 输出契约 + 指向 .dsh/agents/<name>.md）
agent-instructions（读 AGENTS.md）
time-context
[按卡片 tools 字段] tool-fs / tool-fs-search / tool-pwsh / tool-web / tool-todo
skill-filesystem + tool-skill（所有 agent 都能用 Skill）
[tool-subagent ≤1 层] 仅 bootstrap（卡片 max_depth=1 且 tools 含 subagent）
```

## 已知边界（如实记录）

1. **只读靠 persona 约束，不是工具级强制**：`@deepseek-ai/dsh-tool-fs` 同时提供 read/write/edit，无法只给读。11 张只读卡在 persona 里写死「不得修改任何文件、不得执行有副作用命令」，并由 `agent-dispatch` 在派发 prompt 里重复一次。
2. **模型不会自动选 preset**：`subagent` 工具只有在配置了 `allowedAgentPresets` 时才暴露 `agent_preset` 参数。本安装没有覆写内置 preset 的完整插件列表（覆写需重述 40+ 行，升级易碎），因此：
   - ✅ 你可以**新建会话时选 `pcos · <name>`** 作为会话 agent；
   - ⏳ 模型自动委派仍走现有 `agent-dispatch`（组装 prompt 派给通用子 Agent）。
   - 若要让模型自动选，最小改法是在你**自己的** preset 里给 `tool-subagent` 加一行：
     ```yaml
     config:
       provider: spawn
       toolName: subagent
       allowedAgentPresets: [pcos-code-reviewer, pcos-tech-investigator, pcos-knowledge-curator]
     ```
3. **profile 可能被 DSH 重写**：Web 设置页保存时会写 `cordis.patch.yml`。若某次设置变更后发现 preset 不见了，重跑 `kb.py apply-presets` 即可恢复（`check-install` 会报出来）。
4. **新增/修改 agent 后要重新安装**：改 `.dsh/agents/*.md` → `export-presets` → `apply-presets` → 重启。
