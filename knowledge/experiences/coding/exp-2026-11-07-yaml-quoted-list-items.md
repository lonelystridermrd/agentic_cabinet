---
id: exp-2026-11-07-yaml-quoted-list-items
date: 2026-11-07
category: coding/python
domain: coding
problem_type: bug
trigger: "自写的极简 YAML front-matter 解析器遇到带引号的块列表项"
symptom: "校验报错：值 '\"[ ] 需求澄清\"' 不匹配 ^\\[[ xX]\\] .+，引号被当成值的一部分"
root_cause: "内联列表走 _scalar() 会剥引号，块列表项是单独分支直接取原文，两条路径不一致"
fix: "块列表项剥引号后再入数组；同时把仅用于模板的 templates/ 目录排除出条目扫描"
prevention: "同一份数据有两条解析路径时，把「值归一化」抽成共用函数，不要在两个分支里各写一遍。"
tags: [python, parser, yaml, coding]
confidence: high
related: [exp-2026-11-07-template-dir-scanned]
---

## 现象

`kb.py validate` 对任务模板报 5 条 pattern 错误，值里带着字面双引号：

```
subtasks[0]: 值 '"[ ] 需求澄清"' 不匹配 ^\[[ xX]\] .+
```

## 排查过程

1. 先把模板改成不带引号 —— 但 `- [ ] x` 在真 YAML 里会被解析成 flow sequence，属于治标不治本。
2. 回看解析器：内联列表 `[a, b]` 经 `_scalar()` → `_split_inline_list()`，会 `strip("\"'")`；块列表项 `- xxx` 则直接 `data[key].append(item)`。
3. 定位为「两条路径归一化不一致」。
4. 修：块列表项也剥一层成对引号 → 模板保留引号（YAML 合法），解析结果正确。

## 沉淀规则

> 同一份数据有两条解析路径时，把「值归一化」抽成共用函数，不要在两个分支里各写一遍。

同类风险：块标量（`|`/`>`）、注释尾随、`key:` 后空值的布尔语义。当前解析器只覆盖本库用到的子集，遇到新写法先加用例再改代码。
