# 调研报告：嵌入式 Linux 数通平台的多路分发（event loop）方案

- 日期：2026-11-14
- 调研范围：用户态事件分发库/框架，控制面为主、数据面为边界
- 产出性质：**决策材料**，不含最终选择

---

## 0. 摘要

- 候选 11 个 → 收敛 4 个方向（libevent / libuv / 自研 epoll reactor / io_uring）
- 关键发现：
  1. 所有候选在 Linux 上最终都落到 `epoll`（或 `io_uring`），差异在**抽象层、定时器结构、跨线程唤醒、内存模型**，不在"是否用 epoll"。
  2. nginx 的性能优势不来自事件库，来自**每 worker 独立事件循环 + accept 分离/互斥 + 连接池 + 边沿触发读干净**这四件事，任何库都能借鉴。
  3. io_uring 的收益是"减少 syscall + 批量提交"，代价是**内核版本门槛与错误处理复杂度**；在 4.19/5.4 LTS 嵌入式设备上多数特性不可用。
- 实测：**未实测**（本机无 Linux 工具链，WSL 被拒），补齐成本见 §6
- 未知项：目标内核版本、目标 pps/连接数、内存预算、是否可绑核

---

## 1. 范围与约束（待用户确认的假设）

| 类型 | 内容 | 来源 |
|---|---|---|
| 平台 | Linux 用户态，ARM64/MIPS 嵌入式网络设备 | 用户描述 |
| 目标 | 高并发连接 + 低延迟调度，控制面为主 | 用户描述 |
| 硬约束（假设） | 内核 4.19 / 5.4 / 5.10 LTS；内存 128MB–2GB；静态链接优先；体积敏感 | 假设，待确认 |
| 红线 | 无维护项目不可选；核心路径不能依赖外部服务 | 用户已确认 |
| 时间盒 | 广度 1h / 深度 3h | 本次实际 |

---

## 2. 候选全集（广度，11 个，未筛选）

| # | 候选 | 定位（解决哪类问题） | 维护状态 | 许可证 | 备注 |
|---|---|---|---|---|---|
| 1 | libevent | 通用事件通知 + 缓冲 IO，C 生态最老牌 | 2.1.13-stable（2026-07-01） | BSD-3 | 10+ 年生产验证 |
| 2 | libuv | 跨平台异步 IO（Node.js 底层） | 活跃 | MIT | 抽象层最厚 |
| 3 | libev | 极简事件循环，无外部依赖 | 版本更新慢 | BSD-2/GPL 双许可 | 嵌入式体积友好 |
| 4 | 自研 epoll reactor | 精确控制、零依赖 | 自己维护 | 自有 | 需自担正确性 |
| 5 | io_uring + liburing | 减少 syscall、批量提交 | 活跃（内核主线） | MIT（liburing） | 内核版本门槛 |
| 6 | nginx 事件核心 | 工程化参考：ET + 连接池 + accept 分离 | 活跃 | BSD-2 | 不是通用库，借用设计 |
| 7 | FRR thread 调度器 | 数通控制面实践参考 | 活跃 | GPL-2.0 | 需核实细节 |
| 8 | DPDK | 轮询模式数据面，绕过内核 | 活跃 | BSD-3 | 需绑核/大页/独占网卡 |
| 9 | VPP | 基于 DPDK 的用户态协议栈 | 活跃 | Apache-2.0 | 学习/改造成本高 |
| 10 | AF_XDP | 内核旁路但保留驱动框架 | 活跃（4.18+） | GPL-2.0 内核 / MIT 用户态 | 需驱动支持 |
| 11 | 维持现状 | 现有自研/老框架 | — | — | 必选项 |

淘汰标注（只标明显撞红线/约束，不做最终淘汰）：
- #7 FRR：GPL-2.0，若产品闭源交付需评估（未淘汰，仅标记）
- #9 VPP：依赖 DPDK 与特定部署模型，嵌入式资源门槛高（未淘汰，标记）
- #10 AF_XDP：不是"分发库"，是数据面通道（定位不同）

---

## 3. 收敛（4 个方向）

| 结果 | 方向 | 依据 |
|---|---|---|
| 保留 | libevent | 控制面通用、生态最广、BSD 许可、10 年+ 生产验证 |
| 保留 | libuv | 用户点名对比；跨平台；抽象完整 |
| 保留 | 自研 epoll reactor | 数通设备常见做法，体积/依赖最优 |
| 保留 | io_uring | 新内核上的吞吐上限选项 |
| 参考 | nginx 事件核心 | 设计借鉴，不作为库引入 |
| 参考 | FRR 调度器 | 数通控制面实践样本 |
| 淘汰 | libev | 维护活跃度与生态弱于 libevent，功能子集 |
| 淘汰 | DPDK/VPP/AF_XDP | 属数据面方案，超出"多路分发库"边界；可作为后续独立调研 |

> 收敛点需要你确认；不同意可调整。

---

## 4. 方案档案

### 4.1 libevent

**演进**：2000 年代由 Niels Provos 发起 → 2.0（2012，bufferevent/evhttp）→ 2.1（2016–2020，性能与 evbuffer 改进）→ 2.1.13-stable（2026-07-01）。长期处于"稳定维护"阶段，非快速增长。

**原理**
- 后端抽象 `eventop`：Linux 用 epoll，默认**水平触发**，可用 `EV_ET` 显式要求边沿触发。
- 定时器：**小根堆**（timeheap），插入 O(log n)，取最小 O(1)；删除任意定时器 O(log n)（需要定位，实际用惰性删除）。
- 跨线程唤醒：pipe/socketpair 写入触发可读事件。
- IO 缓冲：`evbuffer` 链式缓冲，支持零拷贝 sendfile。

**失败模式**
- 单 `event_base` 多线程需要显式加锁（`evthread_use_pthreads`），否则数据竞争。
- 回调里做阻塞操作会拖垮整个 loop（所有候选通病）。
- 定时器精度受 `epoll_wait` 超时与堆粒度影响，不适合亚毫秒调度。

**证据**：libevent.org（A）、官方 changelog（A）

### 4.2 libuv

**演进**：为 Node.js 而生（2011）→ 跨平台抽象（epoll/kqueue/IOCP）→ 持续活跃。设计目标不是"最快"，是"跨平台一致"。

**原理**
- 单线程事件循环，网络 IO 全部在 loop 线程；fs/DNS/getaddrinfo 走**全局线程池**（默认 4 线程，可 `UV_THREADPOOL_SIZE` 调整）。
- 定时器：堆；`uv_async` 用 eventfd/pipe 唤醒。
- loop 迭代顺序固定：timers → pending → idle → prepare → poll → check → close。

**失败模式**
- 文件 IO 依赖线程池，池满会阻塞（嵌入式上易被误用）。
- 不是线程安全的，跨线程必须 `uv_async`。
- 抽象层厚（handle/request 生命周期规则多），小设备上代码与内存开销高于裸 epoll。

**证据**：docs.libuv.org design（A）

### 4.3 自研 epoll reactor

**原理**
- `epoll_wait` + fd 索引表（数组或 radix），事件回调直接派发；定时器用最小堆或时间轮；跨线程用 `eventfd`。
- 多核：每线程一个 reactor + `SO_REUSEPORT`（Linux 3.9+）或 `EPOLLEXCLUSIVE`（4.5+）分摊 accept。

**引擎侧事实**
- epoll 自 Linux 2.5.44；内核侧是「红黑树（兴趣列表）+ 就绪链表」，`epoll_wait` 只把**就绪事件**拷到用户数组，成本随返回条数线性增长，**不随监视 fd 总数线性增长**。
- 每个注册 fd 约 90B（32 位）/160B（64 位）内核内存；`max_user_watches` 默认 = 可用低内存的 1/25 ÷ 每 fd 开销，超限 `EPOLL_CTL_ADD` 返回 `ENOSPC`。
- ET 必须配非阻塞 fd 并**读到 EAGAIN**，否则会永久丢事件（man 页明确警告）。
- `EPOLLEXCLUSIVE`（4.5+）边界：只能用于 `EPOLL_CTL_ADD`，不能对 epoll fd 使用，与 `EPOLL_CTL_MOD` 互斥；语义是 "one or more" 而非"恰好一个"；ET 下多个线程等同一 epfd 只唤醒一个。
- 嵌套 epoll：一个 epfd 可加入另一个 epfd，但成环或深度 >5 时返回 `ELOOP`；嵌套 + ET 有已知事件丢失报告（LWN 661672，C 级，未核实细节）。

**失败模式**
- ET 下未读干净 → 连接假死；LT 下未读干净 → busy loop。
- fd 复用 + 未从事件表摘除 → 事件投错（对应 pitfalls #18）。
- 定时器漂移、时间回拨（必须 `CLOCK_MONOTONIC`）。

**证据**：man7 epoll(7)（A）

### 4.4 io_uring

**演进**：Linux 5.1 引入；5.4 起单次 mmap；后续加入 multishot accept/recv、registered buffers/files、SQPOLL。属于"上升期"，但**特性随内核版本分层**。

**原理**
- 用户态与内核共享 SQ/CQ 环形队列，批量提交 SQE、批量收割 CQE；`IORING_SETUP_SQPOLL` 让内核线程轮询 SQ，省掉 `io_uring_enter`。
- 减少的是**每次操作的 syscall 与用户/内核拷贝**，不是"事件分发"本身。

**失败模式**
- 内核 <5.1 不可用；4.19 LTS 完全没有；5.4 特性不全（无 SQPOLL_NONFIXED、无 5.19 的 taskrun）。
- 同一 socket 上不允许并发多个 send 或 recv（man 页明确），需 `IOSQE_IO_LINK` 或应用层串行。
- 错误处理复杂（`res` 返回 `-errno`，无 `errno`）；内存序需正确使用 acquire/release。
- 容器 / seccomp 可能禁止 io_uring；6.6 起 `/proc/sys/kernel/io_uring_disabled` 可直接全局禁用（0 允许 / 1 仅特权 / 2 禁用）。
- 历史 CVE 较多（UAF/类型混淆），Android/ChromeOS 曾默认禁用；需确认目标内核补丁级别。

**证据**：man7 io_uring(7)、io_uring_setup(2)（A）

---

### 4.5 内核版本能力矩阵（嵌入式选型的关键约束）

| 内核 | epoll 基础 | EPOLLEXCLUSIVE | io_uring | AF_XDP |
|---|---|---|---|---|
| 4.14 LTS | ✅ | ✅（4.5+） | ❌ | ❌（4.18+） |
| 4.19 LTS | ✅ | ✅ | ❌ | ✅ |
| 5.4 LTS | ✅ | ✅ | ✅（基础，无 SQPOLL_NONFIXED / taskrun） | ✅ |
| 5.10 / 5.15 LTS | ✅ | ✅ | ✅（FAST_POLL、SQPOLL_NONFIXED、POLL_32BITS） | ✅ |
| 6.1 LTS | ✅ | ✅ | ✅（taskrun、SQE128/CQE32） | ✅ |
| 6.6 LTS | ✅ | ✅ | ✅ + `io_uring_disabled` | ✅ |

> 结论：**若目标内核是 4.19 LTS，io_uring 直接出局**；5.4 上只能用到基础能力。厂商 BSP 的 backport 会改变这张表，需以实际内核配置为准。

---

## 5. nginx / FRR 的可借鉴点（不是候选，是设计输入）

| 借鉴点 | nginx 做法 | 对自研/库选型的含义 |
|---|---|---|
| 事件抽象 | `ngx_event_actions` vtable（add/del/enable/disable/add_conn/del_conn/notify/process_events） | 自研时先定这层接口，后端可换 |
| 触发模式 | epoll **ET**（`NGX_USE_CLEAR_EVENT`） | 必须读干净到 EAGAIN，否则丢事件 |
| accept 惊群 | 经典 `accept_mutex` 串行化；1.9.1 起支持 `SO_REUSEPORT`；1.11.3 起用 `EPOLLEXCLUSIVE` 且 `accept_mutex` 默认 off | 多 worker 场景必做，否则空转 |
| 定时器 | 红黑树（`ngx_event_timer_rbtree`，任意节点 O(log n) 增删） | 连接关闭/keepalive 重置需要**按节点删除**，堆要额外索引，红黑树天然支持 |
| 连接管理 | 连接池预分配 + 内存池 | 避免每连接 malloc，降低抖动 |
| 零拷贝 | `sendfile` + buffer chain | 大文件/转发场景收益明显 |
| 进程模型 | 多 worker + CPU 亲和 + reuseport | 扩展性来自"每核一个 loop"，不是库 |

FRR 的 `lib/thread.c` 是数通控制面常见的"自带调度器"路线（定时器 + fd 事件统一封装），细节需以源码为准（本次未逐行核实，标 C）。

---

## 6. 实测（未实测）

**原因**：本机为 Windows，无 `gcc/clang/make`；WSL 报 `Wsl/E_ACCESSDENIED`；无 Docker。无法编译出可比对的产物。

**补齐方案（预计 0.5–1 人日/方案）**：
1. 在目标 Linux（或同架构交叉编译环境）写最小 echo server：libevent / libuv / 自研 epoll / io_uring 各一份。
2. 统一 `-Os -DNDEBUG`、静态链接、`-j1` 编译。
3. 测：`size`（text/data/bss）、`/usr/bin/time -v` 峰值 RSS、启动到 listen 完成的时间、`ldd`/`readelf -d` 依赖、`time make -j1`。
4. 负载：`wrk`/自研压测，1k/10k 连接，P50/P99 延迟，pps。
5. 记录六要素：架构、编译器版本、编译选项、libc、内核、负载模型。

**当前可用的替代证据**：libevent 官网 benchmark 图（D，2010 年代数据，仅参考）；nginx 官方文档（A，但只覆盖机制不覆盖数值）。

---

## 7. 证据表

| # | 结论 | 等级 | 来源 | 日期 |
|---|---|---|---|---|
| 1 | libevent 最新 stable 2.1.13（2026-07-01），BSD-3 | A | https://libevent.org/ | 2026-11-14 |
| 2 | epoll 兴趣/就绪列表、每 fd ~90/160B、`max_user_watches` | A | https://man7.org/linux/man-pages/man7/epoll.7.html | 2026-11-14 |
| 3 | ET 必须非阻塞且读到 EAGAIN，否则可能永久挂起 | A | 同上 | 2026-11-14 |
| 4 | 多线程 ET 只唤醒一个；LT 需 EPOLLEXCLUSIVE 防惊群 | A | 同上 | 2026-11-14 |
| 5 | io_uring 共享 SQ/CQ、SQPOLL、单 socket 串行 send/recv 约束 | A | https://man7.org/linux/man-pages/man7/io_uring.7.html | 2026-11-14 |
| 6 | nginx 支持 EPOLLEXCLUSIVE（Linux 4.5/glibc 2.24），自 1.11.3 | A | https://nginx.org/en/docs/events.html | 2026-11-14 |
| 7 | libuv 单线程 loop、epoll 后端、fs/DNS 走线程池 | A | https://docs.libuv.org/en/v1.x/design.html | 2026-11-14 |
| 8 | libevent 默认 LT、EV_ET 可选；定时器小根堆 | B | 官方文档与源码（未逐行引用） | — |
| 9 | libev 最新 4.33 | C | Debian 打包记录（官网本次不可达） | — |
| 10 | FRR 自带 thread 调度器 | C | 仓库结构（未逐行核实） | — |
| 11 | EPOLLEXCLUSIVE 边界（仅 ADD、不可 MOD、one-or-more） | A | https://man7.org/linux/man-pages/man2/epoll_ctl.2.html | 2026-11-14 |
| 12 | io_uring 能力时间线（5.4 SINGLE_MMAP → 5.11 SQPOLL_NONFIXED → 5.19 taskrun → 6.6 io_uring_disabled） | A | https://man7.org/linux/man-pages/man2/io_uring_setup.2.html | 2026-11-14 |
| 13 | AF_XDP 需 XDP 程序 + XSKMAP；零拷贝依赖驱动 `NETDEV_XDP_ACT_XSK_ZEROCOPY` | A | https://www.kernel.org/doc/html/latest/networking/af_xdp.html | 2026-11-14 |
| 14 | nginx 默认 ET；`accept_mutex` 默认 off 自 1.11.3，改用 EPOLLEXCLUSIVE；1.9.1 起 reuseport | A | https://nginx.org/en/docs/ngx_core_module.html | 2026-11-14 |
| 15 | 各方案产物体积/内存/启动 | — | **未实测** | — |

---

## 8. 条件映射（核心产出，不含"选 X"）

| 若满足 | 更适合 | 依据 |
|---|---|---|
| 内核 <4.5、要零依赖、体积最敏感、团队能承担 reactor 正确性 | 自研 epoll reactor | 无库开销；ET + 读干净 + accept 互斥需自己做对 |
| 控制面万级连接、要最快落地、接受额外依赖 | libevent | 10 年+ 生产验证、BSD、API 稳定 |
| 需要跨平台（含 Windows 开发工具链）、已有异步句柄模型 | libuv | 跨平台一致，但抽象重、fs 走线程池 |
| 内核 ≥5.10、追求减少 syscall/批量提交、能承担复杂度 | io_uring | SQPOLL/批量提交；4.19/5.4 特性不可用 |
| 数据面 >1Mpps、可绑核/大页/独占网卡 | DPDK/VPP（另行调研） | 轮询绕过内核；不是"分发库"范畴 |
| 多核扩展是首要目标（任何库） | 多 reactor + SO_REUSEPORT / EPOLLEXCLUSIVE | 扩展性取决于线程模型，不取决于库 |
| 需要快速验证"够不够快" | 先做 POC 再定 | 体积/内存/延迟必须实测 |

---

## 9. 风险与未知

**风险**
- libevent 2.1 系列多年无大版本，长期看可能进入维护模式（低风险，但需关注）。
- io_uring 在嵌入式 LTS 内核上特性缺失，且历史 CVE 多，需逐版本确认补丁级别。
- 自研 reactor 的隐性成本是**正确性**（ET 丢事件、fd 复用、定时器漂移），不是性能。
- nginx 的 accept_mutex 方案在低连接数下会引入排队延迟；`EPOLLEXCLUSIVE` 也有负载不均问题。

**未知（补齐方式）**
- 目标内核版本 → 直接决定 io_uring 是否在候选内：`uname -r`
- 目标 pps / 连接数 / 延迟预算 → 决定是否需要数据面方案：需求方给数
- 内存与体积上限 → 决定库 vs 自研：给出 KB 上限
- 是否允许动态链接 → 影响体积与部署：构建策略确认

---

## 10. 附录：POC 骨架（补齐实测时用）

```c
/* 自研最小 reactor 骨架（仅示意，不含错误处理） */
int ep = epoll_create1(EPOLL_CLOEXEC);
struct epoll_event ev = { .events = EPOLLIN | EPOLLET, .data.fd = lfd };
epoll_ctl(ep, EPOLL_CTL_ADD, lfd, &ev);
for (;;) {
    int n = epoll_wait(ep, evs, 64, timeout_ms);
    for (int i = 0; i < n; i++) {
        if (evs[i].data.fd == lfd) accept_all(lfd);   /* 循环 accept 到 EAGAIN */
        else drain_read(evs[i].data.fd);              /* 循环 read 到 EAGAIN */
    }
}
```

libevent 对照：

```c
struct event_base *base = event_base_new();
struct event *ev = event_new(base, fd, EV_READ | EV_PERSIST | EV_ET, cb, arg);
event_add(ev, NULL);
event_base_dispatch(base);
```

libuv 对照：

```c
uv_loop_t *loop = uv_default_loop();
uv_tcp_t srv; uv_tcp_init(loop, &srv);
uv_tcp_bind(&srv, (struct sockaddr *)&addr, 0);
uv_listen((uv_stream_t *)&srv, 128, on_conn);
uv_run(loop, UV_RUN_DEFAULT);
```
