# socket 编程手法（Linux 用户态）

> 目标：连接生命周期可控、收发不丢不粘、失败可观测、退出不挂死。

## 1. 传输选型

| 需求 | 选择 | 不选的理由 |
|---|---|---|
| 可靠、有序、可接受队头阻塞 | TCP | — |
| 低延迟、可容忍丢包、自带重传 | UDP + 应用层序号/重传 | TCP 重传会放大延迟 |
| 本机进程间 | Unix domain socket（`AF_UNIX`） | TCP 回环多走一遍协议栈 |
| 与内核/驱动交互 | netlink / ioctl / sysfs | socket 是错层 |
| 一对多、局域网发现 | UDP 多播（`IP_ADD_MEMBERSHIP`） | 广播被路由器丢弃 |

## 2. 生命周期状态机（服务端）

```
CREATED → BOUND → LISTENING → ACCEPTING → ESTABLISHED → CLOSING → CLOSED
                                    ↘ ERROR（记录 → 回到 LISTENING）
```

- 每个状态只允许特定操作（例如 `CLOSING` 时拒绝新数据）。
- 状态迁移必须集中在一个函数里（`session_set_state()`），禁止散落赋值。
- 任何状态都要能回答："此时对端消失会怎样？"

## 3. 必设 socket 选项

| 选项 | 时机 | 原因 |
|---|---|---|
| `SO_REUSEADDR` | `bind` 前 | 重启时避免 `TIME_WAIT` 导致 `EADDRINUSE` |
| `SO_REUSEPORT` | `bind` 前（Linux 3.9+） | 多进程/多线程各自 accept，内核分流 |
| `TCP_NODELAY` | `connect`/`accept` 后 | 小包低延迟场景（控制面）；批量下发可关 |
| `SO_KEEPALIVE` | accept 后 | 只能探测死连接，默认 2 小时太慢 → 改 `TCP_KEEPIDLE/INTVL/CNT` 或用应用层心跳 |
| `SO_RCVBUF/SO_SNDBUF` | 连接建立后 | 高吞吐需显式调大（内核会翻倍），但别指望它解决应用层慢 |
| `SO_LINGER` | `close` 前 | 需要发 RST 快速回收时用；默认别动，否则丢数据 |
| `FD_CLOEXEC` | 创建后立刻 | 防止 `exec` 泄漏 fd（`accept4`/`SOCK_CLOEXEC` 一步到位） |

## 4. 阻塞 / 非阻塞

- 服务端默认：**非阻塞 + epoll**。
- 阻塞模式只用于"确定的短操作"且必须带超时；`SO_RCVTIMEO` 作用于**每次** `recv`，部分读会重置计时，长连接场景不可靠 → 用 `poll` 算截止时间。
- 非阻塞 `connect`：
  ```c
  ret = connect(fd, ...);
  if (ret < 0 && errno != EINPROGRESS) return -errno;
  /* 等 POLLOUT，然后读 SO_ERROR 才知真正结果 */
  ```
- `accept` 在非阻塞下也会 `EAGAIN`，必须当作"暂时没有新连接"而非错误。

## 5. 读循环与帧界定

**铁律：`SOCK_STREAM` 上一次 `recv` 不等于一条消息；`SOCK_DGRAM` 一次 `recv` 就是一个完整报文。**

- TCP 流没有消息边界；UDP 有边界但可能丢、可能乱序，仍要校验长度上界并处理 `MSG_TRUNC`。
- 帧格式优先级：长度前缀（`uint32_t len` + payload）> 固定头 + 变长体 > 分隔符（`\n`）。
- 实现：每连接一个累积缓冲（`buf + cap + len`），`recv` 追加 → `while (可解析一帧) 取帧` → 剩余数据 `memmove` 到头部。
- 缓冲上限：单连接上限（如 1MB），超限视为对端异常并断开，防止内存被打爆。
- 半包：不完整帧留在缓冲里等下次事件，**不要**在 `recv` 返回后假设数据完整。
- 零长度帧：协议里明确是否允许；`recv` 返回 0 是 EOF，不是空帧。

## 6. 写路径与背压

- `send` 返回值 `< len` 是正常现象（尤其非阻塞）：必须续写剩余部分。
- `EINTR` 重试；`EAGAIN` 把剩余数据放进每连接发送队列，注册 `EPOLLOUT`，可写时继续。
- **队列必须有上限**（字节数 + 帧数）；到上限的策略三选一并写明：拒绝新请求（返回错误）/ 丢弃最旧 / 断开连接。
- 禁止无界队列：那就是把 OOM 推迟到流量高峰。
- 批量发送用 `sendmmsg`/`writev` 减少 syscall（Linux 3.0+）。

## 7. 超时三档

| 类型 | 典型值 | 实现 |
|---|---|---|
| 连接超时 | 1–5s | 非阻塞 connect 的截止时间 |
| 读超时 | 按协议，10–60s | 每连接 `last_rx_ms` + 周期扫描 |
| 空闲超时 | 分钟级 | 心跳/keepalive 配合 |

- 统一用 `CLOCK_MONOTONIC` 毫秒；不用 `time()`。
- 扫描用时间轮/最小堆，不要每事件遍历全部连接。

## 8. 关闭流程

1. 停止接收新数据（从 epoll 摘除或标记 `CLOSING`）。
2. 尝试发完发送队列（有上限的等待）。
3. `shutdown(fd, SHUT_WR)` → 读剩余直到 EOF 或超时。
4. `close(fd)`，fd 置 `-1`，结构体标记 `CLOSED`。
5. 释放 per-connection 资源（缓冲、定时器、回调注册）。

- 主动关闭方进 `TIME_WAIT`（默认 60s）；服务端大量短连接要评估端口耗尽。
- `close` 后绝不再用该 fd：fd 会被新连接复用，旧代码路径可能把数据发到别的连接上。

## 9. UDP 要点

- 无连接、不保证顺序/可达；应用层要有序号、去重、超时重传。
- 单个 UDP 报文 ≤ MTU（1500 - IP/UDP 头 ≈ 1472）避免分片；超过要自己分片。
- `connect()` 一个 UDP socket 可固定对端并接收 ICMP 错误，之后用 `send/recv`。
- 多播：`setsockopt(IP_ADD_MEMBERSHIP)` + `SO_REUSEADDR`，绑定 `INADDR_ANY` 或组播地址。

## 10. 多线程/多进程模型

| 模型 | 适用 | 代价 |
|---|---|---|
| 单线程 epoll | 连接数多、每连接逻辑轻 | 一个慢操作阻塞全部 |
| 每连接一线程 | 连接少、逻辑重（阻塞调用多） | 栈内存 × N，上下文切换 |
| 线程池 + 队列 | 请求型负载 | 队列与锁 |
| 多 reactor（`SO_REUSEPORT`） | 多核吞吐 | 连接间共享状态需加锁/分片 |

- `accept` 惊群：`SO_REUSEPORT` 或 `EPOLLEXCLUSIVE`（Linux 4.5+）。
- 每连接对象归属单一 reactor 线程时，可完全无锁（推荐）；跨线程只走消息队列。

## 11. 可观测

- 计数器：连接数、accept 失败、读错误、写队列水位、超时次数、协议错误。
- 日志：状态迁移、异常断开原因（`errno` 原文）、背压触发。
- 排障：`ss -tinp` 看队列与重传；`tcpdump` 抓包对照应用层日志。

## 12. 常见错误速查

见 `../../c-embedded-coding/references/pitfalls.md` 的 #7–#18（短写、EOF、粘包/半包（TCP 专用，UDP 一次一报）、SIGPIPE、SO_REUSEADDR、非阻塞 connect、ET/LT、fd 复用、FD_SETSIZE、select 监听已关闭 fd）。
