---
id: exp-2026-11-14-async-ownership-early-free
date: 2026-11-14
category: coding/ownership
domain: coding
problem_type: bug
trigger: "malloc 出的对象通过注册接口交给其它线程或全局框架后，调用方在注册成功时当场 free"
symptom: "其它线程或框架后续访问已释放内存（UAF），或框架析构时再次释放（double free）；注册失败分支则忘记 free，同一段代码既可能崩也可能泄漏"
root_cause: "所有权边界没有表达清楚：注册接口既不说明『接管』也不说明『借用』，调用方按自己的理解释放；成功与失败两条路径的释放责任没有唯一答案"
fix: "接口名表达所有权（如 xxx_register_take_owns）；成功即转移、调用方不再持有；失败仍归调用方、必须 free；更彻底的做法是让注册函数内部完成分配"
prevention: "跨线程/跨模块注册对象时，函数名必须写明是否接管所有权，成功与失败两条路径各自由谁释放要有唯一答案。"
tags: [c, memory, ownership, concurrency]
confidence: medium
related: []
---

## 现象

崩溃在持有对象的线程里，栈回溯指向注册模块内部；ASan 报 heap-use-after-free 或 double-free。因为存在竞态，复现不稳定，压力越大越容易出现。

## 机制

对象分配在 A 线程/调用方，指针被写入全局注册表后立刻 `free`。注册表里留下悬空指针；B 线程读取时踩空。另一条路径：注册返回失败，调用方认为"函数没接住"，却也没有 free，对象泄漏。根源是"注册"这个动作的所有权语义没被定义。

## 沉淀规则

> 跨线程/跨模块注册对象时，函数名必须写明是否接管所有权，成功与失败两条路径各自由谁释放要有唯一答案。

来源：用户 2026-11-14 口述。本条为机制描述，未附现场日志；confidence=medium。
