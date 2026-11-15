---
id: dec-2026-11-15-iomux-design-choice
date: 2026-11-15
context: 为嵌入式数通平台开发 iomux 多路分发库，需在自研薄封装与成熟事件库之间做正式选型
decision: 自研 libiomux：epoll 水平触发 + EPOLLONESHOT 抑制 + 单 Reactor + 可配置 worker 池 + 每 worker SPSC 队列 + 完成环回 Reactor；不引入 libevent/libuv，不使用 io_uring
alternatives:
  - libevent 2.1.13 + 自研分发层
  - libuv 1.x + 自研分发层
  - io_uring + liburing
rationale: 需求要求原始直接、每 fd 可绑线程、回调进池、LT 固化；成熟库的抽象层与线程模型与这些要求错位，包装后仍要付其事件模型成本。自研仅依赖 epoll/eventfd/EPOLLONESHOT（2.6.x 起），代码量约 1500 行，可在定时器、队列、抑制三个单点上按预算独立选型
consequences:
  - 自研成熟度低，正确性依赖测试与防呆，不依赖十年生产验证
  - 需自行维护定时器堆、SPSC 队列、线程池，约 1500 行
  - 无跨平台能力，只支持 Linux
  - 若内核升至 5.10+ 且 syscall 占比过高，需按反转条件重评 io_uring
confidence: medium
tags:
  - design
  - iomux
  - epoll
  - decision
status: accepted
---

# iomux 设计决策：自研薄封装

## 背景

要交付一个嵌入式数通平台用的多路分发动态库 `iomux`，硬性要求：

- 基于 epoll，**水平触发固化**；poller 可多实例
- 每 poller 监听多个 fd/socket；**单 Reactor**，业务回调进线程池
- 创建时指定线程数；每线程一个 MQ；默认公平调度；单个注册可挂哈希绑定到指定线程
- 基础定时事件；充足防呆；高并发低延迟
- **框架原始直接，不做 libevent 式过度抽象**

已有《事件分发库调研报告》（`2026-11-14-event-dispatch-libs.md`）作为输入材料。

## 需求锚点（假设，未经用户确认）

| 场景 | 连接数 | 事件率 | 派发延迟 P99 | 进程内存 |
|---|---|---|---|---|
| 轻载 | 500 | 20k/s | ≤100µs | ≤8MB |
| 典型 | 4,000 | 200k/s | ≤200µs | ≤32MB |
| 重载 | 8,000 | 500k/s | ≤500µs | ≤64MB |
| 满载（压测上限） | 16,000 | 1M/s + 突发 | 退化可接受，不崩 | ≤128MB |

> 2026-11-15 用户确认采纳以上四档数字（`dec` 已转 accepted）。后续任一数值变更 → 触发下方反转条件重评。

## 报告可信度审计

| 报告结论 | 报告等级 | 本次判断 | 处理 |
|---|---|---|---|
| libevent 2.1.13-stable / BSD-3 | A | 采信 | 版本与许可无争议 |
| EPOLLONESHOT 需 `EPOLL_CTL_MOD` 重挂 | A | 采信 | 直接支撑抑制方案 |
| ET 必须读到 EAGAIN，否则丢事件 | A | 采信 | 本设计用 LT，不受影响，但确认了语义边界 |
| io_uring 在 4.19 不可用（版本推导） | A（版本标注） | 采信 | 作为否决依据 |
| 各库产物体积 / RSS | 未实测 | **存疑** | 不作为依据；需要时自测 |
| nginx `accept_mutex` 1.11.3 起默认 off | A | 采信 | 不影响本设计 |

**独立复核**：重新核对 `epoll(7)`（man-pages 6.19）关于 `EPOLLONESHOT` 的原文——"it is the caller's responsibility to rearm the file descriptor using epoll_ctl with EPOLL_CTL_MOD"。与本设计"oneshot + 完成环重挂"一致；且重挂后若数据未读完，LT 会立即再次上报，因此**语义仍是水平触发**，不是 ET 伪装。

## 七维评估

| 维度 | 自研 libiomux | libevent + 包装 | libuv + 包装 | io_uring |
|---|---|---|---|---|
| 执行效率 | 每事件 1 次 MOD + 1 次 eventfd 唤醒；无 vtable | 额外 event_base 激活队列；抑制需 del/add 两次 syscall | handle/request 生命周期 + 线程池 | syscall 更少，但依赖内核 |
| 内存开销 | ~80B/fd + 40KB/worker 队列 | 同量级 + event_base | 更高（handle/request/loop） | 环内存 + 注册表 |
| 线程开销 | 1 reactor + N worker（N 可配） | 同左，另加库内部锁 | 固定池（fs/dns 也用） | 自建 |
| 数据结构 | fd 哈希 + watcher 池 + 最小堆 | 库内堆 + 自定义 | 库内堆 | SQ/CQ 环 |
| 四场景 | 四档可调参 | 可，但受库抽象牵制 | 可，但模型不匹配 | 4.19 直接出局 |
| 成熟度 | **低**（新代码） | 高（10 年+） | 高 | 中（版本分层） |
| 兼容性 | epoll/eventfd/oneshot，2.6.x+ | 广 | 广 | 5.1+ |
| 解耦 | 薄接口、无全局状态、可替换 | 绑 event_base 模型 | 绑 handle/request 模型 | 绑内核特性 |
| 可扩展性 | 多 poller 实例横向扩展 | 同 | 同 | 同 |

## 单点发散（4 处）

1. **事件抑制**：EPOLLONESHOT（1 次 MOD/事件） vs MOD 关/开（2 次 syscall） vs 仅 busy 标记（LT 下 reactor 自旋）。→ 选 oneshot：syscall 最少且无自旋；代价是依赖 `EPOLLONESHOT`（2.6.2+）。
2. **定时器**：最小堆（带 index，O(log n) 删除） vs 红黑树 vs 时间轮。→ 选堆：容量 ≤1024、按 id 取消需要索引，堆的常数与内存都更小；时间轮在取消场景反而复杂。
3. **队列**：SPSC 无锁环 vs mutex + 批量交换。→ 选 SPSC：生产者只有 reactor，天然单写；push/pop 无锁，延迟 ~20ns 级；代价是每条队列只能一个消费者（正好每 worker 一个）。
4. **分发策略**：轮询 vs work-stealing vs 仅哈希。→ 轮询 + 可选哈希：work-stealing 需要原子操作与跨线程搬运，在"每 worker 独立队列"模型下收益不抵复杂度；哈希已满足绑定需求。

## 场景推演

| 场景 | 推演 | 结论 |
|---|---|---|
| 轻载 20k/s | 每 worker 队列深度 1024，远大于瞬时积压 | 通过 |
| 典型 200k/s | 2 worker 各 100k/s，回调预算 10µs | 通过（回调需保持短） |
| 重载 500k/s | 每 worker 250k/s，队列可能在突发时打满 → 进入 pending 重试 | 退化点是队列深度，不崩 |
| 满载 1M/s | 超出设计点；预期 `queue_full` 上升、延迟退化 | **不以 1M/s 作为 SLO**；压测用于确认"不崩、可恢复" |

**否决判断**：满载场景要求"不崩、可恢复"，当前设计通过（队列满有 pending 重试 + 统计），未触发一票否决。

## 冲突裁决

| 冲突 | 裁决 | 依据 |
|---|---|---|
| 成熟度 vs 需求匹配 | 选自研 | 成熟库的抽象与线程模型无法满足"原始直接 + 每 fd 绑线程"，包装后仍付其成本；成熟度用测试与防呆补偿 |
| 性能 vs 解耦 | 薄接口 + 无 vtable | 两者不冲突：少一层抽象同时降低延迟与耦合 |
| 扩展 vs 简单 | 单 Reactor，不做内部多 reactor | 多核扩展靠**多 poller 实例**（外部 SO_REUSEPORT），不在库内做 YAGNI 设计 |
| 兼容 vs 新特性 | 只用 epoll/eventfd/oneshot | 不引入 io_uring，保住 4.19 兼容 |

## 最终选择

自研 `libiomux`，架构为：

```
reactor 线程：epoll_wait(LT) → 选 worker → SPSC 入队 → eventfd 唤醒
worker 线程：出队 → 执行回调 → 写完成环 → eventfd 唤醒 reactor
reactor：完成环出队 → epoll_ctl MOD 重挂（EPOLLONESHOT）
定时器：reactor 内最小堆；周期定时器到点重挂，回调未完则丢该 tick（不补发）
跨线程注册：命令队列 + 同步等待（返回准确错误码）
```

## 否决项

- **io_uring**：假设内核 4.19 → 无此特性（兼容红线）。
- **libevent 包装**：可行但抑制需 del/add 两次 syscall，且 event_base 激活队列与"原始直接"冲突。
- **libuv 包装**：抽象最重，固定线程池（fs/dns 共用）与"业务回调池"模型不匹配。

## 反转条件（可观测）

1. 目标内核 ≥5.10，且实测 `perf stat` 显示 epoll/eventfd 相关 syscall 占 CPU >30% → 重评 io_uring。
2. 满载压测 `queue_full` 持续 >5% 或出现事件丢失 → 引入多 reactor 或换库。
3. 团队无测试资源维护 1500 行 → 退回 libevent 包装（约 2 人日）。
4. 需求锚点任一数值与假设偏差 >2× → 重新评估 worker 数、队列深度与是否多实例。

## 代价与回退

- 迁移成本：0（新库，无存量调用方）。
- 回退成本：换 libevent 包装层约 2 人日，换 libuv 约 3 人日。
- 放弃的能力：跨平台、十年生产验证、内置 bufferevent/HTTP 等生态。

## 置信度理由

medium：epoll/EPOLLONESHOT/LT 语义有 A 级原文支撑，架构推理可逐条验证；但无本平台实测，且需求锚点四个数尚未经用户确认。
