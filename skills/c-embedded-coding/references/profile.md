# 项目基线 profile（唯一可调参数入口）

> 改这里 = 改整套规范的行为。**只允许两类修改**：① 用户明确拍板；② `experience-interview` 回收后经用户确认。
> 每次修改在本文件末尾追加一行变更记录，不覆盖历史。

## 生效参数

| 参数 | 当前值 | 说明 / 允许的替代 |
|---|---|---|
| 平台 | Linux 用户态（app / 协议栈 / CLI） | 内核态、RTOS、裸机不在本 Skill 覆盖范围 |
| C 标准 | `gnu11` | `c99`（无 `_Static_assert` 等）、`gnu17` |
| 缩进 | **Tab（强制）**，一级 = 1 Tab（宽 8） | 禁止空格缩进；`.editorconfig` 固定 `indent_style=tab` |
| 续行对齐 | Tab 到语句缩进层，其余用空格推齐 | 参数各占一行时只加 1 Tab，不追列对齐 |
| 行宽 | 120 列 | 日志字串字面量豁免 |
| 大括号 | K&R（函数独占一行，控制语句同行） | — |
| 初始化写法 | `{0}` | `{ 0 }`（内核风格） |
| 模块前缀 | 按模块名 snake_case（`vlan_`、`sock_`） | — |
| 全局变量前缀 | `g_` | 无前缀（若项目已有约定） |
| typedef | 结构体**不 typedef**；整型别名 `_t`；函数指针 `_cb`/`_fn`/`_handle` | 连整型别名也不用（纯内核风格） |
| 错误码 | `0` 成功 / 负 `errno` 失败 | 项目私有码表（`-1000` 起）需另建映射 |
| 指针失败返回 | `NULL` + 头注释说明 | `ERR_PTR` 风格 |
| 日志宏 | `dbg_printf(fmt, args...)`，前缀 `__func__(__LINE__).` | 分级宏（`LOG_E/W/I/D`）在此之上扩展 |
| 日志实现 | 业务模块自研，不用 syslog/rsyslog；禁止裸 `printf/fprintf` | 生产用编译期开关整体切掉 DEBUG |
| 注释 | **英文 + Doxygen**（`/** */`、`@brief/@param/@return/@note`） | 规范/知识库文档中文 |
| 实现注释 | 只写三类：设计策略、未实现分支、严重踩坑 | 不复述字面意义 |
| 断言策略 | `assert` 只用于内部不变量，生产可关 | 生产保留 `ASSERT`（重启前先 dump） |
| 时间基准 | `CLOCK_MONOTONIC` | — |
| 内存策略 | 启动期分配，运行期用固定池 | 运行期 `malloc` 需注明上限与失败处理 |
| 线程栈 | **默认 8 MB**，按 `RLIMIT_STACK` 取值，`pthread_attr_setstacksize` 显式设置 | 不依赖 libc 默认值；调小需核算最坏调用深度 |
| 线程创建 | 允许运行期 `pthread_create` | 必须显式 attr + 检查返回值 + 明确 join/detach |
| 编译开关 | `-Wall -Wextra -Werror -Wshadow -Wpointer-arith -Wcast-align -Wstrict-prototypes -Wmissing-prototypes -Wformat=2 -Wimplicit-fallthrough -Wswitch-enum` | `-Wconversion`（噪声大，默认关） |
| 函数规模 | 150 行原则（非硬上限）；编排类可突破，步骤须同层；参数 ≤5 | 超 150 行走「单一输出 / 目的内聚 / 编排同层」三问并写结论 |

## 待确认（TBD）

已全部关闭（2026-11-14），结论已回填上表。新问题追加到本段，不覆盖历史。

- [x] 是否有现成的 `.clang-format` / 公司规范文档 → 当前无；后续有则以文档为准并回填本表
- [x] 项目是否用 C99 VLA → 禁用
- [x] 是否允许 `goto` 之外的异常风格（`setjmp/longjmp`） → 禁用
- [x] 线程栈默认大小与运行期 `pthread_create` → 8 MB，按 rlimit 显式设置；允许运行期创建
- [x] 日志系统 → 业务模块自研；统一封装宏，禁止裸 `printf/fprintf`

## 变更记录

| 日期 | 改了什么 | 依据 |
|---|---|---|
| 2026-11-14 | 初始版本：Linux 用户态 + kernel style 裁剪 + MISRA 子集 | 用户 2026-11-14 确认 |
| 2026-11-14 | 函数行数上限 60/80 → 200（同步 SKILL.md 闸门与 style.md S6） | 用户直接修改 SKILL.md 闸门 |
| 2026-11-14 | 200 → 150 原则，取消硬上限；新增「单一输出 / 目的内聚 / 编排同层」三问，编排类可突破 | 用户 2026-11-14 口述 |
| 2026-11-14 | 缩进改为 Tab 强制（取消用户态 4 空格）；续行规则改为「Tab 到层 + 空格对齐」 | 用户 2026-11-14 口述 |
| 2026-11-14 | 注释改为 Doxygen + 英文；公共接口必写 NULL 契约/所有权/上下文；实现注释限定三类 | 用户 2026-11-14 口述 |
| 2026-11-14 | 行宽 100 → 120 | 用户修订 profile |
| 2026-11-14 | TBD 全部关闭：线程栈 8 MB + 读 rlimit + 显式设置；日志自研、统一 `dbg_printf`；允许运行期 `pthread_create` | 用户修订 profile |
| 2026-11-14 | switch 收紧：全部必须 `default`、贯穿处必须 `/* fall through */`；编译开关加 `-Wimplicit-fallthrough -Wswitch-enum` | 用户 2026-11-14 口述 |
