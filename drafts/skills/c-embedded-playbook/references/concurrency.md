# 线程上下文与并发手法

> 先定**谁在什么上下文里执行**，再谈锁。多数并发 bug 源于"忘了这段代码跑在哪个线程"。

## 1. 线程模型选型

| 模型 | 适用 | 代价 | 共享状态 |
|---|---|---|---|
| 单线程事件循环 | 连接多、每事件短 | 慢操作阻塞全部 | 几乎无（无锁） |
| 每连接一线程 | 连接少、有阻塞调用 | 栈内存 × N（默认 8MB，可调小） | 需锁或消息传递 |
| 线程池 + 队列 | 请求型、CPU 密集 | 队列锁、任务粒度 | 队列是唯一共享点 |
| 流水线（每阶段一线程） | 阶段耗时差异大 | 阶段间队列、背压 | 边界的无锁队列 |
| 多进程 | 隔离性、崩溃不扩散 | IPC 成本、状态同步 | 共享内存/消息 |

**默认**：网络 IO + 轻逻辑用单线程 epoll；CPU 密集段拆到线程池。

## 2. 上下文标注（写进函数头注释）

每个可能被多处调用的函数必须标注：

- 可阻塞？可持锁调用？可在信号处理函数里调？线程安全？
- 例：`/* 上下文：会睡眠（内部取 mutex），禁止在中断/信号处理/持锁路径调用 */`

> 没有上下文标注的函数，一律视为"只能在主线程、无锁、不阻塞"。

## 3. 锁的层次与顺序

- 全局定义锁层级：`config_lock(1) < session_lock(2) < stats_lock(3)`。
- 规则：**只能按序号递增获取**；逆序即死锁。
- 持锁期间禁止：IO、回调、`malloc/free`、`sleep`、`pthread_join`、任何可能阻塞的调用。
- 临界区尽量小：先算好再取锁，锁内只做赋值/查表。
- 不要用"递归锁"掩盖设计问题；同一线程重复加锁说明调用链没理清。

## 4. 同步原语选择

| 场景 | 原语 | 注意 |
|---|---|---|
| 短临界区、无睡眠 | `pthread_mutex`（默认） | 优先，行为清晰 |
| 读多写少 | `pthread_rwlock` | 写者可能饥饿；读锁内不能升级 |
| 极短、无阻塞 | 自旋锁（`pthread_spinlock`） | 只在确定不睡眠时用，否则浪费 CPU |
| 单个计数器/标志 | `_Atomic` / `__atomic_*` | 注意内存序，默认 `seq_cst` 最安全 |
| 跨线程传递指针/数据 | 无锁队列（SPSC/MPSC） | 需要正确的 acquire/release |
| 等待条件成立 | 条件变量 | 必须 `while` 循环；超时用 `CLOCK_MONOTONIC` |
| 一次性初始化 | `pthread_once` | 不要手写双重检查（除非用原子） |

- `volatile` 不是同步原语：只用于 MMIO 和信号标志。
- 引用计数用 `_Atomic int` + `fetch_sub`，归零者负责释放；注意"先取指针再增引用"的竞态（需要 RCU 或锁）。

## 5. 无锁队列（SPSC）要点

```c
/* 生产者 */
tail = atomic_load_explicit(&q->tail, memory_order_relaxed);
next = (tail + 1) & q->mask;
if (next == atomic_load_explicit(&q->head, memory_order_acquire)) return -EAGAIN; /* 满 */
q->buf[tail] = item;
atomic_store_explicit(&q->tail, next, memory_order_release);

/* 消费者 */
head = atomic_load_explicit(&q->head, memory_order_relaxed);
if (head == atomic_load_explicit(&q->tail, memory_order_acquire)) return NULL; /* 空 */
item = q->buf[head];
atomic_store_explicit(&q->head, (head + 1) & q->mask, memory_order_release);
```

- 容量取 2 的幂；留一个空位区分满/空。
- 多生产者必须 CAS 循环或加锁；不要"假装是 SPSC"。
- 元素是指针时，注意对象生命周期（消费者释放 vs 生产者复用）。

## 6. 线程创建与退出

- `pthread_create` 检查返回值；`pthread_attr_init` 后**显式** `pthread_attr_setstacksize`——默认按 8 MB 配置，实际取值先 `getrlimit(RLIMIT_STACK)`，不要依赖 libc 的默认参数（版本/环境不同会变）。
- 运行期允许创建线程，但必须：显式 attr（栈大小、detach 状态）、检查返回值、明确谁负责 join；禁止在循环里无上限创建。
- 线程名：`pthread_setname_np`（≤15 字符），便于 `top -H`/`gdb`。
- 退出：置停止标志（原子）→ 唤醒（条件变量/eventfd）→ `pthread_join` → 释放资源。
- **不要用 `pthread_cancel`**：取消点不可控，清理不彻底；用协作式退出。
- 线程函数返回值用 `void *`，必要时传错误码出来。
- 分离线程（detach）只用于"永不关心结果"的场景，且要保证资源自清理。

## 7. 信号与线程

- 信号处理函数只碰 `volatile sig_atomic_t`，其它一律转事件循环（`signalfd` / self-pipe）。
- 多线程进程里信号可能投递给任意线程：启动时把所有信号屏蔽，再在专用线程 `sigwait`。
- `SIGPIPE` 在 socket 程序里统一忽略（或 `MSG_NOSIGNAL`）。

## 8. CPU 亲和与实时性

- 热路径线程绑核（`pthread_setaffinity_np`），减少迁移与 cache 失效。
- 实时线程（`SCHED_FIFO`）只用于硬实时段，且要防止优先级反转（用优先级继承 mutex）。
- 绑定前确认核数足够，别把管理线程和 IO 线程绑到同一核。

## 9. 可观测

- 每线程：CPU 占用、队列深度、锁等待时间（`pthread_mutex` 无内建统计，需自己打点）。
- 死锁排查：`gdb -p` + `thread apply all bt`；`pstack`；`/proc/<pid>/task/*/stack`（内核态）。
- 记录：谁持有锁、等了多久、哪个线程持锁时间异常长。

## 10. 常见错误

见 `../../c-embedded-coding/references/pitfalls.md` 的 #28–#33（volatile 轮询、持锁回调、锁序、条件变量、系统时间、信号处理）。
