---
name: sop-executor
description: 按 .dsh/knowledge/sops/ 里的 SOP 执行：匹配触发、逐步跑检查点、记录偏差并回写版本。适用"按 SOP 来""走一遍流程""有流程文档吗"。
whenToUse: 用户说"按 SOP 走""执行标准流程""这个流程之前定过吗""照上次的步骤来"；或同一类任务已有 sop-* 条目而本次要再执行一次。
---

# sop-executor — SOP 执行

## 触发条件

- 库里已有 `sop-*` 条目，且本次任务命中其 `trigger`
- 任务步骤 ≥4 步、有检查点、需要跨会话复现
- 用户明确要求「按标准流程/上次的步骤」执行

**不触发**：一次性操作；SOP 触发条件不匹配（不硬套，转 `make-skill` 判断要不要新建）；纯探索（转 `research-assistant`）。

## 输入

- 任务一句话目标与完成判据
- SOP ID 或领域（`coding`/`research`/`ops`/`review`）
- 执行环境：分支、权限、依赖版本、可回退点
- 上次执行的偏差记录（若有）

## 步骤

1. **匹配 SOP**：`python .dsh/tools/kb.py search <关键词> --type sop`，必要时加 `--domain <domain>`。
   **完成判据**：得到唯一 SOP 路径与 `version`；命中 ≥2 条时按 `trigger` 逐条比对后只选 1 条，并写明淘汰理由。
2. **读全文**：读 `.dsh/knowledge/sops/<domain>/<slug>.md` 的 front-matter 与正文的「步骤」「检查点」两段。
   **完成判据**：能复述 `trigger`、`estimated_time`、检查点数量；三项任一缺失即停，先补 SOP。
3. **预检前置条件**：逐条核对权限、分支/备份、依赖版本、回退点。
   **完成判据**：每项给出 yes/no + 证据（命令输出或路径）；有 no 且不可消除 → 停手报阻塞。
4. **逐步执行**：按编号执行，每步记录「动作 / 实际输出摘要 / 检查点结果」。
   **完成判据**：每步都有命令或动作 + 可观察结果；无空步。
5. **记偏差**：出现跳步、改序、命令失败、耗时 > `estimated_time` 的 150% 之一即记一行偏差。
   **完成判据**：偏差表每行含 步骤号 / 现象 / 原因 / 绕行 / 是否需回写 SOP；零偏差也要显式写「无」。
6. **回写版本**：偏差导致步骤或检查点变化时，更新 SOP 正文并把 `version` 加 0.1、`last_updated` 改为当天。
   **完成判据**：diff 只含变更段；版本号与日期同步；无变化则不升版本。
7. **收口**：`python .dsh/tools/kb.py validate` → `python .dsh/tools/kb.py index`；踩坑 >10 分钟转 `experience-capture`；任务卡勾选子任务。
   **完成判据**：validate 零 error；任务卡 `subtasks` 与进度日志一致。

## 质量闸门

- [ ] SOP 存在且 `trigger` 与本次任务逐字比对过
- [ ] 每个检查点都有通过/不通过证据
- [ ] 偏差表存在（零偏差写「无」而非留空）
- [ ] 改了步骤就升 `version` 并更新 `last_updated`
- [ ] 未擅自修改 SOP 的 `trigger` 与 `domain`
- [ ] 超时或失败步骤已转 `experience-capture` 或记入阻塞
- [ ] `kb.py validate` 零 error

## 输出格式

```
执行：<sop-id> v<旧> → v<新>（<路径>）
结果：完成 <n>/<m> 步 · 检查点 <x>/<y> 通过
偏差：
| 步骤 | 现象 | 原因 | 绕行 | 回写 |
待处理：<阻塞 / 经验条目 / 无>
```

## 反面清单

- ❌ 触发条件不匹配还硬套 SOP——先停，别用流程掩盖不适配。
- ❌ 执行中随手改 SOP 不记版本——下次无法判断该信哪版。
- ❌ 检查点「看起来没问题」就跳过——检查点必须留下证据。
- ❌ 把一次性操作沉淀成 SOP——出现第 2 次再抽象。
- ❌ 偏差只在对话里说，不落表——下次执行会重犯。

## 用例

**成功用例**：用户说「按 SOP 发一次版」。`kb.py search 发布 --type sop` 命中 `sop-ops-release`；预检 6 项全 yes；10 步执行，第 7 步耗时超预估 2 倍记偏差，回写 `estimated_time` 与版本号；validate 零 error。

**边界用例**：用户说「按 SOP 建个前端项目」，但库里只有 `sop-coding-feature-development`，`trigger` 是「已有仓库内改功能」。判定不匹配 → 不执行，输出「现有 SOP 不覆盖初始化场景，建议先跑一次再沉淀」，而不是把功能开发 SOP 套到建项目上。
