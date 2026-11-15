---
id: exp-2026-11-14-memcpy-one-sided-length-check
date: 2026-11-14
category: coding/memory-bounds
domain: coding
problem_type: bug
trigger: "调用 memcpy 时，长度 n 只对 src 或 dst 其中一侧做过容量校验"
symptom: "短的一侧被越界读或越界写，崩溃点通常不在 memcpy 调用处；表现为相邻变量被改、栈被踩、堆元数据损坏，换优化级别后现象变化"
root_cause: "把「n 对某一侧合法」当成「n 合法」；memcpy 同时读 src 与写 dst，任一侧可用长度小于 n 就越界"
fix: "调用前分别断言 src_len >= n 与 dst_len >= n；把指针与长度成对封装成结构，接口只接受带长度的缓冲"
prevention: "任何 memcpy/memmove 前，src 与 dst 的可用长度都要各自 >= n，只校验一侧等于没校验。"
tags: [c, memory, memcpy, bounds]
confidence: medium
related: []
---

## 现象

越界写发生在短的一侧，但崩溃/异常往往出现在后续无关代码里：相邻栈变量被改、堆块头被破坏导致 free 时 abort。

## 机制

`memcpy(dst, src, n)` 要求 `[src, src+n)` 与 `[dst, dst+n)` 都可访问。只检查 `n <= dst_len` 或只检查 `n <= src_len` 时，另一侧仍可能越界。长度校验写成单侧，通常源于"这个参数是从我这边传出去的，我这边够就行"的假设。

## 沉淀规则

> 任何 memcpy/memmove 前，src 与 dst 的可用长度都要各自 >= n，只校验一侧等于没校验。

来源：用户 2026-11-14 口述。本条为机制描述，未附现场日志；confidence=medium，待补充一次真实现场后升级为 high。
