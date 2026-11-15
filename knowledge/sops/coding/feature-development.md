---
id: sop-coding-feature-development
domain: coding
name: feature-development
version: 1.0
last_updated: 2026-11-07
trigger: "接到新功能需求（有明确交付物，需改动代码）"
estimated_time: "30min-2day"
---

# 功能开发 SOP

## 适用与不适用

- 适用：新增功能、行为变更、接口扩展，有可验收的交付物。
- 不适用：纯 bug 修复（走 `incident-responder` 的轻量路径）、纯重构（走 `refactor-planner`）。

## 步骤

1. **需求澄清** — `spec-writer`
   - 输入：用户原话 + 相关决策
   - 输出：目标 / 非目标 / 接口契约 / 验收标准 / 风险
   - 完成判据：验收标准每条可判定，用户确认
2. **历史查证** — 自己
   - `python .dsh/tools/kb.py search <关键词>`
   - 完成判据：引用 ≥1 条决策，或明确写「无先例」
3. **方案设计** — 自己 +（必要时）`refactor-planner`
   - 输出：接口定义 + 关键取舍；不可逆点走 `decision-logger`
   - 完成判据：决策条目已落库（若涉及选型）
4. **实现** — 自己
   - TDD 优先：先写失败测试再实现
   - 完成判据：测试通过 + 手工验证路径
5. **自检** — `code-reviewer`（派发见 `agent-dispatch`）
   - 完成判据：无 P0/P1；P2 已记录或修复
6. **记录** — `experience-capture` / `decision-logger`
   - 完成判据：本次新坑入 `exp-*`、新选型入 `dec-*`，`kb.py validate` 0 error

## 检查点

- [ ] 需求已澄清且用户确认（验收标准可判定）
- [ ] 方案与已有决策无冲突，或冲突已标注 `supersedes`
- [ ] 测试覆盖核心路径与边界
- [ ] 审查无 P0/P1
- [ ] 经验与决策已记录，索引已重建（`kb.py index`）

## 偏差记录

| 日期 | 偏差 | 处理 | 是否回写 SOP |
|------|------|------|--------------|
| 2026-11-07 | 首版建立，尚未有真实执行记录 | — | 待首次执行后回填 |
