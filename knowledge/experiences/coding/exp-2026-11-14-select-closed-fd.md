---
id: exp-2026-11-14-select-closed-fd
date: 2026-11-14
category: coding/fd-lifecycle
domain: coding
problem_type: bug
trigger: "select 的 fd_set 里仍保留已经 close 掉的套接字"
symptom: "select 返回 EBADF；若该 fd 号已被新连接复用，select 会持续报可读/可写，事件被投递到错误对象，表现为消息错乱、连接假死或忙循环"
root_cause: "close 不会把 fd 从 fd_set 或事件注册表里摘除；内核按 fd 号复用，旧位仍指向新对象，位含义已经变了"
fix: "所有关闭统一走一个函数：先从 fd_set/注册表移除，再 close，最后把 fd 置 -1；结构体加状态位阻止重复关闭"
prevention: "close 前先摘除监听注册，close 后立即把 fd 置 -1；禁止在其它地方直接调用 close。"
tags: [c, socket, select, fd-lifecycle]
confidence: medium
related: []
---

## 现象

`select` 返回 -1 且 `errno == EBADF`；或者更隐蔽：fd 号被新连接复用后，`FD_ISSET` 一直为真，代码去读一个"没数据的新连接"，形成空转或把旧连接的逻辑套到新连接上。

## 机制

`fd_set` 只是位图，`close(fd)` 释放的是 fd 号，不会回写任何位图。下一次 `socket()` 很可能拿到同一个最小可用 fd 号，于是位图里那一位重新"有效"，但指向的是另一个对象。

## 沉淀规则

> close 前先摘除监听注册，close 后立即把 fd 置 -1；禁止在其它地方直接调用 close。

来源：用户 2026-11-14 口述。本条为机制描述，未附现场日志；confidence=medium。
