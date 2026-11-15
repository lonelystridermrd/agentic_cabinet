# 安全规则 A1–A31（MISRA-C:2012 裁剪版）

> 只保留在**用户态 Linux 嵌入式**环境下真正会咬人的条款。未列入的 MISRA 条款默认不强制
> （例如 15.x 对 `goto` 的全面禁止、17.8 参数不可修改、21.6 全面禁用 stdio —— 这些在
> Linux 工程里不现实）。
>
> **偏差不是违规，不记录才是违规。** 每条例外必须在 diff 或头注释里写一句理由。

## 资源与返回值

### A1 检查所有可能失败的调用（MISRA Dir 4.7 / 17.7）
- 判据：`malloc/calloc/realloc/open/socket/accept/read/write/send/recv/pthread_*/fopen/fclose/clock_gettime` 的返回值必须被判断。
- 明确忽略时写 `(void)` 并加一句理由，例如 `(void)close(fd); /* 只读 fd，close 失败无副作用 */`。
- 例外：`close()` 对普通 fd 可忽略；**写文件/日志的 close 必须判断**（错误可能延迟到 close 才返回）。

### A2 动态内存只在启动期（MISRA Dir 4.12）
- 判据：运行期热路径（每包、每事件、每请求）禁止 `malloc/free`；启动期分配后不再释放。
- 原因：分配延迟不可控、碎片不可控、OOM 无路可退。
- 例外：低频配置路径可分配，但必须有**上限**与失败处理（返回 `-ENOMEM`，不是 abort）。

### A3 资源逆序释放，单一 cleanup（MISRA 22.1）
- 每个函数最多一个 `out:`；释放顺序与获取顺序相反。
- 判据：所有 return 前要么在 `out:` 之后，要么显式释放；`goto out` 是唯一允许的 goto 用法。

### A4 `free` 后置 NULL，禁止双重释放
- `free(p); p = NULL;` 成对写；结构体释放后把指针字段一并置空。
- 判据：同一指针在函数内出现 `free` 两次即可疑（除非中间重新赋值）。

## 类型与整数

### A5 禁止隐式窄化转换（MISRA 10.3）
- 判据：`uint8_t x = value;`（value 更宽）必须显式 `(uint8_t)` 并**先做范围检查**。
- 反例：`uint16_t len = ntohs(hdr->len); pkt->len = len;`（`pkt->len` 是 `uint8_t` 时静默截断）。

### A6 有符号与无符号禁止混合运算（MISRA 10.4）
- 判据：比较、加减、位运算两侧类型符号一致；不一致先转成更宽的无符号。
- 经典坑：`for (int i = len - 1; i >= 0; i--)` 里 `len` 是 `size_t` → 比较永远为真。
- 无符号减法先判大小：`if (a < b) return 0; diff = a - b;`。

### A7 所有边界必检（MISRA 18.1）
- 数组/缓冲区访问前检查 `idx < len`；`memcpy` 前检查 `dst_len >= n`。
- 接口设计上让"指针 + 长度"成对出现，不要只传指针。
- 反例：`buf[len] = '\0';` 而 `buf` 大小正好是 `len` → 越界 1 字节（最常见的堆破坏）。

### A8 整数溢出检查（MISRA 12.x 工程扩展）
- 分配前：`if (count > SIZE_MAX / size) return -ENOMEM;`
- 加法前：`if (a > UINT32_MAX - b) ...`
- GCC/Clang 用 `__builtin_add_overflow` / `__builtin_mul_overflow`，比手写判断可靠。
- 反例：`malloc(n * sizeof(*p))`（n 来自报文）。

### A9 移位安全（MISRA 12.2）
- 移位量必须 `< 位宽`；写 `1u << n` 而不是 `1 << n`；不对负数和有符号数右移（实现定义）。
- 掩码用无符号常量：`0xFFFFu`。

### A10 位域禁止用于协议解析（MISRA 6.x / 工程规则）
- 位域布局是实现定义的（大小端、是否跨字节）；协议字段用显式掩码 + 移位。
- 反例：`struct hdr { uint8_t ver:4; uint8_t ihl:4; };` 直接对报文 `memcpy`。

### A11 指针转换与对齐（MISRA 11.x）
- 禁止无对齐保证的指针转换；`(struct foo *)buf` 前确认 `buf` 对齐。
- packed 结构体成员**不要直接取址**，用 `memcpy` 到局部变量后再用（ARM/MIPS 上非对齐访问会 SIGBUS）。

### A12 未初始化读取（MISRA 9.1）
- 所有局部变量声明即初始化；结构体 `= {0}`；数组 `= {0}`。
- 判据：`-Wmaybe-uninitialized` 打开；编译器不报不代表没有（跨函数路径）。

## 字串与内存操作

### A13 禁用危险字串函数（MISRA 21.x 工程扩展）
- 禁止：`strcpy/strcat/sprintf/gets/alloca`。
- 用：`snprintf`（首选）、`strlcpy/strscpy`（有则用）、`memcpy` + 显式长度。
- 判据：`snprintf` 返回值 `>= size` 表示**被截断**，必须处理（返回错误或标记）。
- 反例：`strncpy(dst, src, sizeof(dst));` 不保证 NUL 结尾。

### A14 `memcpy` 长度必须来自可信来源，且两侧都校验（MISRA 19.1）
- 长度不能直接来自报文/外部输入，必须先与本地缓冲大小比较。
- **两侧都要校验**：`n` 必须同时满足 `src_len >= n` 与 `dst_len >= n`。只校验一侧是"修好一个坑、挖出另一个"的典型。
- 重叠内存用 `memmove`。

### A15 空指针与失效指针（MISRA 17.x）
- 解引用前判空**仅对可能为空的来源**（返回值、可选参数、表查找结果）；对内部必不为空的指针反复判空说明契约不清。
- 禁止返回局部变量的地址；`static` 缓冲返回必须注释"非线程安全"。

## 控制流

### A16 禁止递归（MISRA 17.2）
- 栈在嵌入式里通常 8–64KB；递归深度不可控。用显式栈或迭代重写。
- 例外：编译期可确定的固定深度（如 3 层解析树）可接受，需注释深度上限。

### A17 `switch`：必须有 `default`，无 `break` 必须写 `/* fall through */`（MISRA 16.x）
- **所有 `switch` 一律写 `default`**，包括"枚举已穷举"的情形——不设例外。
- 故意贯穿（case 末尾没有 `break`）的，必须在贯穿点写 `/* fall through */`，精确用这几个词；否则 `-Wimplicit-fallthrough` 报错。
- 同时开 `-Wswitch-enum`：有了 `default` 之后，只开 `-Wswitch` 会吞掉"新增枚举成员未处理"的告警，`-Wswitch-enum` 补回这个能力。
- `default` 不要静默 `break`：真不可达就写 `default: /* unreachable */ break;`；能收到非法值就记一条 ERROR 日志并返回错误，别让非法值悄悄通过。
- 想避免贯穿又不愿复制代码，把公共逻辑抽成函数，而不是靠贯穿省事。

### A18 `goto` 只允许向前跳到 cleanup（MISRA 15.x 裁剪）
- 禁止跳入循环、禁止向后跳、禁止跨函数初始化跳过。
- 唯一允许形态：`if (err) goto out;` 到同函数末尾标签。

## 并发与上下文

### A19 `volatile` 不是同步原语（MISRA 工程规则）
- 只用于：MMIO 寄存器、`volatile sig_atomic_t` 信号标志、`setjmp` 保护变量。
- 多线程共享数据用 `_Atomic` / 互斥锁 / 明确的内存屏障；`volatile` 只阻止编译器优化，不保证可见性与原子性。

### A20 信号处理函数只用 async-signal-safe 函数
- 允许：`write`、`_exit`、`kill`、`sig_atomic_t` 赋值。
- 禁止：`malloc`、`printf`、`syslog`、`pthread_mutex_lock`、任何可能分配或加锁的调用。
- 推荐：`signalfd` 或 self-pipe，把信号转成事件循环里的普通事件。

### A21 锁的契约写进注释
- 每个共享结构体注释"由哪个锁保护"；持锁期间禁止：IO、回调、`malloc`、`free`、`sleep`。
- 锁顺序全局定义（如 `config_lock < session_lock`），任何逆序都是死锁。
- 判据：一个函数里出现两把锁时，必须在注释里写出顺序依据。

### A22 条件变量必须在 `while` 中等待
- 判据：`while (!cond) pthread_cond_wait(...)`；用 `if` 是虚假唤醒 bug 的来源。
- 超时等待用 `pthread_cond_timedwait` + `CLOCK_MONOTONIC`，不用 `gettimeofday`。

## 时间、断言与其它

### A23 超时与间隔只用单调时钟（MISRA 工程规则）
- `CLOCK_MONOTONIC` 做超时、间隔、耗时统计；`CLOCK_REALTIME` 只用于"给人类看的时间"。
- 反例：用 `time(NULL)` 判断超时 —— NTP 回拨会让超时立刻触发或永不触发。

### A24 `assert` 不用于外部输入校验（MISRA 工程规则）
- `NDEBUG` 下 `assert` 被编译掉；对外部输入、可恢复错误一律返回错误码。
- `assert` 只用于"绝不可能发生"的内部不变量，且生产配置下是否保留由 profile 决定。

### A25 头文件不定义可变对象
- 头文件里 `int g_count;` 在多个 TU 中会重复定义（C99 tentative definition 行为差异）。
- 正确：头文件 `extern int g_count;`，一个 `.c` 里定义。

### A26 函数指针调用前判空，回调生命周期写明
- 注册的回调必须说明：调用上下文、是否可重入、对象销毁时是否自动注销。

### A27 禁止魔术数字（MISRA 工程规则）
- 超时、重试、长度、端口、协议号、数组维度全部具名；同一个数字出现在两处即缺陷来源。

### A28 浮点运算（MISRA 14.x）
- 无 FPU 的平台（多数 MIPS/ARM 嵌入式）避免 `float/double`；`%f` 打印会拉入软浮点。
- 计数、金额、时间不用浮点；必须用时统一比较用 epsilon，不用 `==`。

### A29 端序与对齐（MISRA 工程规则）
- 协议字段 `htons/htonl/ntohs/ntohl`；结构体禁止直接 `send/recv`（padding + 端序）。
- `__attribute__((packed))` 仅用于线上格式，本地处理用展开的结构体。

### A30 未定义行为要有检测网（MISRA 工程规则）
- CI 至少跑一轮 `-fsanitize=address,undefined`（用户态可行）；嵌入端跑 `valgrind` 或自研 alloc 计数。
- 重点抓：越界、UAF、双重释放、有符号溢出、未对齐访问。

### A31 `scanf` 家族格式符必须与目标宽度匹配（MISRA 21.6 工程扩展）
- `%x`/`%u`/`%d` 写入的是 `unsigned int`/`int`（通常 4 字节），把 `char *`/`short *` 传进去就是 4 字节越界写，踩坏相邻栈变量。
- 正确做法：先解析到 `unsigned int`，范围检查后再窄化；或使用长度修饰 `%hhu`/`%hx`/`%hu`。
- 优先 `strtoul`/`strtol` + `endptr` + `errno`：返回值可控，也不依赖格式串。
- 同理 `scanf("%s", buf)` 无宽度限制等同 `gets`，必须写显式宽度（如 `%31s`，且为 NUL 留位）。
