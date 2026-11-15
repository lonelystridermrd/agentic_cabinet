---
id: sop-review-knowledge-maintenance
domain: review
name: knowledge-maintenance
version: 1.0
last_updated: 2026-11-07
trigger: "每周一次，或 kb.py validate 出现 error 时"
estimated_time: "15-30min"
---

# 知识库巡检 SOP

## 适用与不适用

- 适用：周期性维护知识库结构、索引与条目质量。
- 不适用：单条内容的撰写（那是 decision-logger / experience-capture 的职责）。

## 步骤

1. **结构校验** — 自己
   - `python .dsh/tools/kb.py validate`
   - 完成判据：error 0；warning 逐条判定「修 / 留」
2. **索引重建与抽查** — 自己
   - `python .dsh/tools/kb.py index`，再抽 3 个关键词检索
   - 完成判据：每个关键词都能定位到预期条目，跨类型命中正常
3. **扫描重复与孤儿** — `knowledge-curator`（派发）
   - 扫描 `decisions/` `experiences/` `sops/`，找重复 ID、同主题多条目、无入链的孤儿条目
   - 完成判据：重复题给出「合并/保留」建议，孤儿条目给出归属或废弃建议
4. **tag 词表收敛** — 自己
   - `python .dsh/tools/kb.py tags`，同义词合并、低频 tag 改为已有 tag
   - 完成判据：无同义 tag 并存（如 `auth` 与 `authentication`）
5. **过时标记** — `knowledge-curator`
   - 被取代的条目改 `status: superseded` 并指向新 ID
   - 完成判据：无「已失效但仍为 accepted」的条目
6. **复发问题升级** — `pattern-spotter`
   - 检查 `patterns/recurring-issues.md`，复发 ≥2 次要给出「升级为硬规则 / 工具层拦截」的建议
   - 完成判据：每条复发项都有处置状态

## 检查点

- [ ] `validate` 0 error
- [ ] `index` 已重建且抽查 3 个关键词命中正常
- [ ] 重复与孤儿条目已处置（合并/保留/废弃建议）
- [ ] tag 无同义词并存
- [ ] 无失效却仍 `accepted` 的决策
- [ ] 复发问题有升级建议
- [ ] 巡检结论已写入当日 daily-log

## 偏差记录

| 日期 | 偏差 | 处理 | 是否回写 SOP |
|------|------|------|--------------|
| 2026-11-07 | 首版建立，首次巡检将在下一周执行 | — | 待首次执行后回填 |
