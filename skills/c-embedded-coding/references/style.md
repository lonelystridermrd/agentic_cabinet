# 风格规范 S1–S13（Linux kernel style 裁剪）

> 基准：K&R / Linux kernel coding style。差异点已标 **[裁剪]**，理由写在各条后面。
> 所有参数（缩进、行宽、前缀）以 `profile.md` 为准；本文件给的是**判定方法**，不是教条。

## S1 缩进与对齐（Tab 强制）

- **缩进一律用 Tab**：一级 = 1 个 Tab（显示宽 8）。禁止用空格做缩进；`.editorconfig` 固定 `indent_style = tab` / `tab_width = 8`。
- 判据：行首出现空格、且不属于续行的对齐段 → 违规。同一文件里 Tab 与行首空格混用，直接打回。
- **续行（同一条语句换行）**：先用 Tab 推到第一行语句的缩进层级，其余用**空格**推齐到左括号后或运算符对齐列。**Tab 只管层级，空格只管列。**
- 示例（`→` 表示一个 Tab）：
  ```c
  →ret = send_packet(session, buf, len,
  →→→  flags);        /* 3 个 Tab 到语句缩进层，再用空格对齐到 len 之后的列 */
  ```
  对齐基准是**首行左括号后的第一列**。若参数各占一行（括号后直接换行），续行只加 1 个 Tab，不再追求列对齐。
- 声明块的 `=` 对齐不做强制（`= {0}` 无需对齐），避免加变量时整块重排；要对齐只允许用空格补列，禁止用 Tab 补列。

**[裁剪] 为什么不用内核的 80 列**：日志串、路径、协议字段名在现代代码里普遍超 80，硬折行反而降低可读性。行宽取 120；超 120 的**日志字串字面量**可豁免，但拼接处按语义断行。

## S2 大括号与空行

- 函数定义：左括号 `{` **独占一行**。
  ```c
  static int vlan_add_port(struct vlan *v, uint16_t port)
  {
  ```
- 控制语句：左括号**同行** `if (x) {`、`for (...) {`、`switch (x) {`。
- 单语句分支可省略括号，但**出现 `else` 或多行时必须加**；嵌套 ≥2 层一律加。
- `else` 与前一右括号同行：`} else {`；`do {` … `} while (cond);` 同一行收尾且带分号。
- 函数之间空一行；函数内逻辑段落之间空一行；连续变量声明后空一行再写语句。
- 文件末尾保留一个换行；不留连续 2 个以上空行。

## S3 空格

- 关键字后：`if (`、`for (`、`while (`、`switch (`、`return (` 例外（`return` 后不空格）。
- 函数名与括号之间**无**空格：`foo(a, b)`；宏名与括号之间也**无**：`MAX(a, b)`。
- `sizeof(x)`、`typeof(x)`、`alignof(x)` 括号贴紧。
- 一元运算符贴紧：`!flag`、`~mask`、`-1`、`++i`、`*p`、`&x`。
- 二元运算符两侧各一空格：`a + b`、`p->len == n`、`i << 2`。
- `,` 后一空格、前无；`;` 前无；`->`、`.` 两侧无。
- 指针声明：`char *p`（星号贴变量），`char **pp`；强制转换 `(uint32_t)x` 括号内无空格。
- 数组下标无空格：`buf[i]`；初始化 `{ 0 }`（内核风格）或 `{0}`（用户态）**按 profile 二选一**，同一文件不混用。

## S4 命名

| 对象 | 规则 | 例 |
|---|---|---|
| 函数 / 变量 | snake_case，模块前缀 | `vlan_add_port`、`sock_state` |
| 文件级 static | 模块前缀（可选 `s_`） | `vlan_find_by_id` |
| 全局变量 | `g_` 前缀 **[裁剪]** | `g_vlan_table` |
| 结构体 | **不 typedef**，直接写 `struct foo`（全小写） | `struct pkt_buf`、`struct iomux_poller` |
| 整型别名 | `_t` 后缀，仅用于基础整型/核心概念的扩展 | `time_t`、`seqno_t`、`pkt_len_t` |
| 函数指针 | `_cb` / `_fn` / `_handle` 后缀，**不用 `_t`** | `iomux_cb`、`compare_fn` |
| 宏 / 编译期常量 | 全大写 | `MAX_PKT_LEN` |
| 枚举值 | 类型前缀 + 全大写 | `PKT_STATE_DROP` |
| 布尔 | `is_` / `has_` / `can_` | `is_running` |
| 带单位 | 后缀带单位 | `retry_ms`、`len_bytes` |

- **禁止** `typedef struct foo foo_t;`：结构体名就是 `struct foo`，指针写 `struct foo *`；`_t` 只留给整型与标准库风格的类型。不透明类型同样直接用 `struct foo *`，不另造别名。
- 函数指针 typedef 按语义挑后缀：`_cb`（回调）、`_fn`（策略/比较/哈希）、`_handle`（事件处理）；`_t` 结尾的函数指针一律视为命名错误。
- 长度：局部变量 ≤ 20 字符、全局 ≤ 24；模块前缀不算超长理由的反面——**前缀是必须的**。
- 禁止拼音（`chakan`）、禁止无意义缩写（`tmp2`、`data1`）；`buf`/`ctx`/`cfg`/`fd`/`len` 属公认缩写，允许。
- 同名不同单位必须区分：`timeout_ms` vs `timeout_s`。
- 宏与枚举不得重名（S13 的 `-Wmacro-redefined` 兜不住无声覆盖）。

**[裁剪] `g_` 前缀**：内核不用，但用户态多模块工程里裸全局变量极易与局部变量混读。若项目已有约定，按项目。

## S5 声明与定义

- 局部变量**在块首声明并初始化**（C90 兼容，也避免"声明后忘了赋值"）。C99 允许就近声明，但同一函数内风格统一。
- 禁止一行声明多个不同类型的变量：`int i, *p;` ❌。
- 指针声明与解引用分开：`char *p = NULL;` 而不是 `char* p`。
- 函数返回 `void` 时原型写 `(void)`，定义写 `(void)`；调用时传参给 `(void)` 函数直接编译报错。
- 数组参数退化为指针时**必须**同时传长度：`int copy(char *dst, size_t dst_len, const char *src)`。
- `const` 用在两处：不改的入参（`const char *`）、不改的指针目标（`char * const`）。不需要"const 一切"，但要挡住写错。

## S6 函数形状

- 行数：**150 行是原则，不是硬上限**。不超过 150 行不必为拆而拆；超过也不强制拆——先判断，再决定。
- 超过 150 行时，除原有的结构切分判断（能否按"取数 / 校验 / 执行 / 收尾"分段）外，必须回答三问：
  1. **输出是否单一**：只有一个返回值、一个出参，或只写一处共享状态？多个输出通常意味着背了多个职责。
  2. **目的是否内聚**：能否用一句话概括整段代码且不出现"并且"？出现"并且"就是两个函数。
  3. **是否编排类**：函数体主要是"调用子步骤 + 顺序/条件控制 + 失败处理"，自身不做重计算？
- **编排类允许突破 150 行**，但被编排的步骤在整体业务流程中必须处于**同一层次**（例如都属"会话建立阶段"）。混层——一半"建立连接"、一半"解析某个字段"——不是编排，是职责不清，按层次拆。
- 拆分不是目标：拆完各段仍然只能一起改、只能一起测，说明拆错了。
- 参数：≤ 5；超限用上下文结构 `struct foo_ctx *`，但 ctx 必须是**只读**且生命周期覆盖调用。
- 嵌套：≤ 3 层 `if`；第 4 层用 early return 或抽函数。
- 出口：**不强制单出口**。推荐内核模式——正常路径直接 `return`，错误路径统一 `goto out`，`out:` 之后只有清理与返回。
  ```c
  ret = -ENOMEM;
  p = malloc(len);
  if (!p)
          goto out;
  ...
  ret = 0;
  out:
          free(p);
          return ret;
  ```
- 顺序：`out:` 标签内的释放顺序与获取顺序**相反**。
- 同一函数内不要混用"多 return + goto"两套风格；跟随文件现状。

## S7 头文件

- guard：`#ifndef MOD_FILE_H` / `#define MOD_FILE_H` / `#endif /* MOD_FILE_H */`；不用 `#pragma once`（跨编译器/旧工具链一致性）。
- include 顺序，组间空行：
  1. 自身头（`foo.c` 先 `#include "foo.h"`，用于暴露缺失依赖）
  2. 标准库 `<stdint.h>`
  3. 系统/第三方 `<sys/socket.h>`、`<pthread.h>`
  4. 本项目头 `"vlan.h"`
- 每个头**自足**：单独 `#include` 能编过，不依赖"调用方先包含了什么"。
- 头文件只放：类型声明、宏、`extern` 函数原型、`static inline` 小函数。**禁止**定义变量、禁止 `static` 函数（会造成每个 TU 一份副本）。
- 公共头只暴露跨模块契约；内部结构放 `foo_internal.h`，且不许被模块外 include（用 `#error` 或目录约定挡）。

## S8 注释（Doxygen，英文）

**语言与风格**

- 注释一律**英文**（标识符、日志串同）。中文只出现在规范与知识库文档里。
- 对外接口用 Doxygen：`/** ... */` 配 `@brief` `@param` `@return` `@retval` `@note` `@warning`；文件头用 `@file` `@brief`；结构体字段用 `/**< ... */` 行尾注释。
- 只写**对外核心作用与契约**，不写实现细节——实现细节由代码本身表达。

**公共接口必须写清的契约（缺一即不合格）**

- 形参能否传 `NULL`，传 `NULL` 的语义：可选参数？禁用并返回错误？走默认值？
- 所有权：谁分配、谁释放；是否接管入参。
- 调用上下文：可阻塞？内部取锁？线程安全？能否在信号处理函数里调用？
- 返回值/错误码：哪些可重试，哪些是终态。
- 重要用法注意点：是否必须先调某个函数、能否重复调用、调用后对象是否失效。

```c
/**
 * @brief Add a port to a VLAN member table.
 *
 * @param v    VLAN object. Must not be NULL and must outlive the call.
 * @param port Port index, 0..MAX_PORT-1.
 * @param name Optional member name. NULL means unnamed; "" is invalid.
 *
 * @return 0 on success, -EEXIST if already a member, -ENOSPC if the table is full.
 *
 * @note May sleep (takes an internal mutex). Do not call with a spinlock held
 *       or from a signal handler.
 */
int vlan_add_port(struct vlan *v, uint16_t port, const char *name);
```

**函数注释（全部函数，硬性）**

- **每个函数定义（含 `static`）上方必须有块注释**：做什么、参数含义、返回值/错误、调用上下文。
- 公共函数用 Doxygen（契约以头文件为准，实现处可写"See iomux.h"）；**内部函数同样用 `/** ... */` 且必须有 `@brief`**，有参数/返回值时补 `@param`/`@return`。
- 关键流程（状态迁移、加锁/原子、顺序约束、错误回滚、边界条件）在代码处写**为什么**，不是复述"做什么"。
- 判定：`python .dsh/tools/comment_audit.py <src>` 必须 `0 missing`（只认 `/**` + `@brief`）；L0 不通过不得写下一个文件。

**实现过程注释：只在三类场合写**

1. **设计决定 / 实现必须遵守的策略**（不变量、顺序约束、为什么这样选）——让 reviewer 能判断代码是否忠实表达设计，也让后续迭代不把关键逻辑改错：
   ```c
   /* Publish the pointer only after all fields are visible. Do not move this
    * store above the memcpy: readers acquire it without taking the lock. */
   ```
2. **代码「没有实现」的分支**——某场景明确不执行、但代码里没有对应分支时，用注释说明：
   ```c
   /* No retry on -EAGAIN here: retry policy belongs to the caller (session_loop). */
   ```
3. **踩过的严重问题**——写明原因与"不要这样改"，避免维护人再踩：
   ```c
   /* Do not free pkt->buf here: it is owned by the packet pool. Freeing it
    * caused a double free under stress (2026-11). */
   ```

**不写什么**

- 不复述字面意义：`i++; /* increment i */` 这类直接删。
- 不解释显而易见的函数名；不写"历史实现"（git 会记得）。
- 密度不是越高越好：一个函数头 + 3~5 处关键点足够；超过了说明代码本身没把意图表达清楚。

- `TODO(name):` / `FIXME(name):` 必须带名字，无主 TODO 视为死代码；注释掉的代码直接删。

## S9 类型与整数

- 定长类型优先：`uint8_t/uint16_t/uint32_t/uint64_t`、`int8_t…`；跨边界（协议、共享内存、持久化、日志二进制）**禁止**裸 `int/long`。
- 长度用 `size_t` 做内部计算，但**结构体字段与协议字段不用 `size_t`**（宽度随架构变）。
- `char` 只表示字符；字节用 `uint8_t`；`char` 参与算术是常见事故源。
- 布尔用 `<stdbool.h>` 的 `bool`，不用 `int` 当 bool；`if (flag)` 优于 `if (flag == 1)`。
- 枚举：需要跨边界/落盘/打日志时**显式赋值**并留 `XXX_MAX`；纯内部状态机可不赋值。
- 指针与整数互转只在 `uintptr_t` 上做，且加注释说明用途。

## S10 常量与宏

- 编译期常量优先 `enum`（可调试）或 `static const`；`#define` 只用于：条件编译、需要字符串化（`#x`）、数组维度（C99 VLA 不允许时）。
- 多语句宏必须 `do { ... } while (0)`；参数全部加括号；宏体不引用外部变量。
- 宏参数禁止带副作用：`MAX(i++, 0)` ❌；函数式宏优先改 `static inline`。
- 宏名与普通标识符不重名；`#undef` 只在收尾清理时用，不在中途反复定义同名宏。

## S11 错误码与返回值

- 统一一种：Linux 用户态用 **`0` 成功 / 负 `errno` 失败**（`-EINVAL`）；不要混用"返回 -1 并设 errno"和"返回负 errno"两套。
- 函数返回指针时：失败返回 `NULL` 且**不**设 errno，或返回 `ERR_PTR` 风格——二选一并写进头注释。
- 错误码要**可区分**：`-EINVAL`（参数错）、`-ENOMEM`（内存）、`-EAGAIN`（暂时不可）、`-ETIMEDOUT`（超时）、`-ECANCELED`（取消）。禁止所有失败都 `return -1`。
- 错误路径必须能回答："调用方拿到这个码会做什么？" 答不上来说明码设计有问题。

## S12 日志

- **禁止业务代码直接调 `printf/fprintf`**，统一走自研封装宏。默认形态：
  ```c
  #define dbg_printf(fmt, args...) printf("%s(%d)." fmt "\n", __func__, __LINE__)
  ```
  三个要点：`fmt` 必须是**字面量**（与 `"%s(%d)."` 拼接后 `-Wformat` 才能查类型）；生产版用编译期开关整体切掉；要兼容 C99 就写 `...` + `__VA_ARGS__`，GNU 的 `args...` 只在 `gnu11` 下可用。
- 分级：`ERROR`（影响功能，需人看）/ `WARN`（可自愈但异常）/ `INFO`（状态迁移）/ `DEBUG`（排障），在封装宏之上扩展。
- 热路径（每包、每事件）只允许 `DEBUG`，且用编译期开关编译掉；`ERROR` 在热路径必须限速（计数器 + 周期汇总）。
- 格式串与参数类型必须匹配：`%zu`（size_t）、`PRIu64`（uint64_t）、`%p`（指针）、`%s` 不接受 NULL（用 `(p ? p : "(null)")`）。
- 一条日志只讲一件事，不要 `"recv failed, len=%d, fd=%d, state=%d, ..."` 拼 8 个字段——排障时 grep 不动。
- 禁止在信号处理函数、`atexit` 回调里用 `printf`/`syslog`（非 async-signal-safe）。
- 日志内容禁止打印秘钥、完整报文（截断到前 16 字节 + 长度）。

## S13 编译与告警

- 基线开关：`-Wall -Wextra -Werror -Wshadow -Wpointer-arith -Wcast-align -Wstrict-prototypes -Wmissing-prototypes -Wformat=2 -Wimplicit-fallthrough -Wswitch-enum`。
- `-Wimplicit-fallthrough` 要求贯穿处写 `/* fall through */`；`-Wswitch-enum` 保证有 `default` 时新增枚举成员仍会告警（见 safety A17）。
- 追加（按 profile 决定）：`-Wconversion`（团队能扛住噪声就开）、`-Wundef`、`-Wvla`、`-Wdouble-promotion`。
- 标准固定：`-std=gnu11`（或项目既定），不默认依赖 `-std=gnu17` 的新特性。
- 结构体初始化用 `= {0}`；局部数组也初始化（避免未初始化读取被优化成任意值）。
- 禁止依赖编译器扩展，除非用 `#if defined(__GNUC__)` 包起来并提供降级实现。
- 反例：`uint32_t x = -1;`（隐式转换 + 实现定义）、`long len = 0xFFFFFFFF;`（32 位平台截断）。
