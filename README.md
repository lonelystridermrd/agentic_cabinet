# `.dsh/` — 个人认知操作系统（Personal Cognitive OS）

> 版本 v1.0 · 建立于 2026-11-07 · 基线文档：`../DSH个人认知操作系统_整体规划.md`
> 一句话：把经验、决策逻辑与工作流固化为可复用能力，并让系统随使用自我演进。

## 三层结构（对应规划第 1 节）

```
认知沉淀层   knowledge/{decisions,experiences,sops,patterns,daily-logs,agent-calls}
编排决策层   skills/（15 个 Skill）+ agents/（17 张 persona 卡片）+ AGENTS.md
执行工具层   tools/kb.py + tools/selftest.py + DSH 内置工具（read/write/edit/grep/glob/pwsh/subagent/web_*）
```

## 目录说明

| 路径 | 放什么 | 由谁写 |
|---|---|---|
| `knowledge/decisions/` | 决策条目 `dec-*` + 自动索引 | `decision-logger` |
| `knowledge/experiences/<domain>/` | 经验条目 `exp-*` + 自动索引 | `experience-capture` |
| `knowledge/sops/<domain>/` | SOP `sop-*` + 自动索引 | `sop-executor` / `make-skill` |
| `knowledge/patterns/` | 好模式 / 反模式 / 复发问题 | `pattern-spotter` |
| `knowledge/daily-logs/` | 每日工作日志 | `bootstrap` |
| `knowledge/agent-calls/` | 子 Agent 派发日志（jsonl，可统计） | `agent-dispatch` |
| `knowledge/.index/` | 派生索引（json），**禁止手改** | `kb.py index` |
| `tasks/{active,backlog,done/YYYY-MM}` | 任务卡 `TASK-*` | `task-tracker` |
| `skills/<name>/SKILL.md` | DSH 自动装载的 Skill | `make-skill`（经 drafts 确认） |
| `drafts/skills/<name>/` | **不被装载**的 Skill 草稿沙箱（G3） | `make-skill` |
| `agents/<name>.md` | 子 Agent persona 卡片 | `architect` / `make-skill` |
| `schemas/` | 5 份 JSON Schema（decision/experience/sop/task/agent） | `architect` |
| `tools/kb.py` | 索引、检索、校验、新建、晋升、调用日志 | `architect` |
| `docs/` | 命名规范、模板、演练记录 | 人 + `architect` |

## 与 DSH 的对接事实（实测，2026-11-07）

| 事实 | 值 |
|---|---|
| Skill 发现根（优先级） | `<projectRoot>/.dsh/skills`(100) → `<projectRoot>/.agents/skills`(200) → custom(300) → `~/.dsh/skills`(400) → `~/.agents/skills`(500) |
| `projectRoot` 定义 | 含 `.git` 的最近祖先；没有则用 cwd |
| Skill 形态 | `<name>/SKILL.md`（或扁平 `<name>.md`）；嵌套 `**/SKILL.md` **不会**被发现 |
| 必填 front-matter | `name` + `description`；可选 `whenToUse`、`metadata`、`disable-model-invocation`、`user-invocable` |
| `name` 约束 | `^[a-z0-9]+(-[a-z0-9]+)*$`，不匹配则**静默跳过**（无报错） |
| 热更新 | 目录被 watch，新增/改名/删除后下一次模型步骤即生效，无需重启 |
| 子 Agent 真实性 | DSH 的子 Agent 由 preset 插件树定义，**不扫描** agents 目录；安装时由 `kb.py export-presets` 把卡片转成 `@deepseek-ai/dsh-agent-preset` 声明写入 profile |

## 日常六条命令

```powershell
python .dsh/tools/kb.py search 认证      # 检索（决策/经验/SOP/任务/模式 五类）
python .dsh/tools/kb.py validate         # 校验（schema + 命名 + Skill/Agent/草稿一致性）
python .dsh/tools/kb.py index            # 重建 4 份 markdown 索引 + JSON
python .dsh/tools/kb.py board            # 从任务卡重建 TRACKING.md 看板
python .dsh/tools/kb.py check-install    # 核对 Skill/preset 是否仍装着
python .dsh/tools/selftest.py            # 工具自检（24 用例，改 kb.py 后必跑）
```

## 安装到 DSH

工作区是**源**，安装副本在 DSH 侧。详见 [`.dsh/install/README.md`](install/README.md)。

```powershell
python .dsh/tools/kb.py install --scope user   # 15 个 Skill → %DSH_HOME%/skills（免重启）
python .dsh/tools/kb.py export-presets         # 17 个 agent → preset 补丁（生成 + 自校验）
python .dsh/tools/kb.py apply-presets          # 追加到 profile 补丁（备份 + 校验，需重启）
python .dsh/tools/kb.py check-install          # 核对安装状态
python .dsh/tools/kb.py remove-presets         # 回滚 preset
```

| 类型 | 落点 | 生效 |
|---|---|---|
| Skill ×15 | `%DSH_HOME%\skills\<name>`（rank 400 用户根） | 免重启（目录被监视） |
| Agent ×17 | `%DSH_HOME%\profiles\<profile>\cordis.patch.yml` 的 `pcos presets` 区块 | 重启 DSH 后出现在 agent 列表 |

改了 `.dsh/agents/*.md` 或 `.dsh/skills/*` → 重跑对应 install/export+apply；`check-install` 会告诉你哪里过期了。


Windows 提示：若在 pwsh 里看到 `UnicodeEncodeError: 'gbk' codec`，先 `$env:PYTHONUTF8=1`（见 `exp-2026-11-07-gbk-python-stdout`）。

## 总循环

```
日常任务 → 执行记录(daily-log/agent-calls) → 经验抽取(experience-capture)
     ↑                                                    ↓
辅助决策(检索/引用) ← 匹配检索(kb.py search) ← SOP/决策/经验入库(decision-logger / sop-executor)
```

## 演进节奏

- **每次会话**：`bootstrap` 启动规程（daily-log → active tasks → 按 tag 检索 → 今日优先级 ≤3）
- **每周**：`weekly-review` 出周报 + `evolution-tracker` 出使用统计与 ≤3 条演进提案
- **每月**：`pattern-spotter` 聚类复发问题，把 ≥2 次复发的坑升级为硬规则或工具层拦截
- **闸门**：任何能力新增/合并/废弃都先出提案，由人确认后才动 `AGENTS.md` 与正式目录
