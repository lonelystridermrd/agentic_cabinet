---
id: exp-2026-11-07-asar-offset-relative
date: 2026-11-07
category: debugging/binary-format
domain: debugging
problem_type: knowledge
trigger: "想从 app.asar 里按 header 记录的 offset 直接读某个文件内容"
symptom: "按 header 的 offset 前缀 read 出来是错位内容（读到的是别的 JS 代码片段），文件长度对得上但内容不对"
root_cause: "asar header 中每个 file 的 offset 是相对 data section 起点的偏移，不是整个归档文件的绝对偏移；data section 起点 = 8 + header pickle 长度"
fix: "先解析 header JSON 得到其长度与 data section 起点，再用 dataStart + offset 定位；或不用 offset，直接在整档里搜索目标文本片段"
prevention: "读 asar 等带 header 的归档时，任何 offset 先确认它是相对谁的，再决定是否加基址；不确定就直接按内容搜索。"
tags: [asar, binary-format, electron, tooling]
confidence: high
related: [exp-2026-11-07-gbk-python-stdout]
---

## 现象

需要确认 DSH 的 Skill 发现规则，于是扫描 `app.asar` 里的 `SKILL.md` 与 README。按 header 里 `"offset": "12742836"` 直接切片，得到的是 `dsh-client` 的 TypeScript 源码片段，而 header 声明的文件是 `agent-experience/SKILL.md`（2093 字节）。

## 排查过程

1. 核对长度：切出的 2093 字节确实是完整的一段代码，不是截断 → 说明基址错了但长度对。
2. 检查 asar 格式：文件头部为 `uint32 4` + `uint32 headerSize` + header JSON，随后才是 data section；header 内 offset 相对 data section。
3. 改用「在整档中搜索目标文本」的方式交叉验证，能直接读到正确的 SKILL.md 内容（asar 不压缩）。
4. 结论：offset 是相对偏移，直接当绝对偏移用会整体前移 data section 起点那么多字节。

## 沉淀规则

> 读 asar 等带 header 的归档时，任何 offset 先确认它是相对谁的，再决定是否加基址；不确定就直接按内容搜索。

附带结论（本次真正要查的事）：DSH 的 Skill 发现根包含 `<projectRoot>/.dsh/skills`（rank 100）与 `~/.dsh/skills`（rank 400），格式为 `<name>/SKILL.md`，`name` 必须匹配 `^[a-z0-9]+(-[a-z0-9]+)*$`，否则**静默跳过**。
