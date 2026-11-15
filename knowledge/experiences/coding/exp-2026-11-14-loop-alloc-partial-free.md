---
id: exp-2026-11-14-loop-alloc-partial-free
date: 2026-11-14
category: coding/error-path
domain: coding
problem_type: bug
trigger: "循环里逐个 malloc，中途某次失败时只释放当前这一个条目就返回错误"
symptom: "前几轮已成功分配的内存失去所有引用，进程常驻内存随调用次数单调增长，长时间运行后 OOM；重启即恢复，容易误判为『内存缓慢泄漏』"
root_cause: "错误路径只处理了『当前这一次』，没有回滚循环开始前已成功分配的对象；缺少统一的清理入口"
fix: "记录循环起始下标或已成功数量，失败时从起始位置 free 到当前位置；或改为一次性分配整块，成功后只维护切片"
prevention: "循环内分配失败必须回滚到循环开始前的状态，不是只释放当前这一条。"
tags: [c, memory, error-path, rollback]
confidence: medium
related: []
---

## 现象

功能"只是偶尔失败一次"，但失败过的进程内存不回落；连续触发失败后 RSS 持续上涨。

## 机制

循环体里 `p[i] = malloc(...)`，失败分支 `free(p[i])` 后 `return -ENOMEM`。`p[0..i-1]` 仍有效但没有任何指针再指向它们（局部数组随函数返回消失），形成不可回收的泄漏。

## 沉淀规则

> 循环内分配失败必须回滚到循环开始前的状态，不是只释放当前这一条。

来源：用户 2026-11-14 口述。本条为机制描述，未附现场日志；confidence=medium。
