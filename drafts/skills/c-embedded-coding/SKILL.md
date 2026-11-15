---
name: c-embedded-coding
description: 嵌入式 C 编码规范与安全底线（Linux kernel style 裁剪 + MISRA 子集）：类型、布局、错误路径、资源释放、整数与字串、日志。适用"写个 C 函数""按规范改""审一下这段 C"。
whenToUse: 新增或修改 C 源文件/头文件、review 一段 C 代码、判断某写法是否合规；或用户说"按我们的编码规范来""这段 C 有没有问题""帮我按风格整理一下"。
---

# c-embedded-coding — 嵌入式 C 编码规范执行

> 规范是**可判定的**：每条都能指出文件行号。写不出"错在哪一行、违反哪一条"，就等于没审。

## 触发条件

- 新增 `.c` / `.h`，或改现有 C 函数（含重构、搬移、加日志、改错误处理）
- 自审或 review 他人 C 代码
- 判定"这么写行不行"（类型转换、指针所有权、内存、错误码、宏）
- **不触发**：只改注释错别字；只调参数不碰结构；纯 Makefile / 脚本 / 配置

## 输入

1. 目标文件与所属模块前缀（如 `vlan_`、`sock_`）
2. 基线参数：`references/profile.md`（缩进、行宽、错误码、日志宏、断言策略）
3. 该文件现有的错误处理与日志惯例 —— 先读相邻 50 行，**跟随现状**，不自创第二套
4. 若仓库有 `.clang-format` / `.editorconfig`：以它为准，profile 退让

## 步骤

1. **读基线**：确认缩进、行宽、模块前缀、错误码风格、日志宏五项；`.clang-format` 存在时先 `clang-format --dry-run -Werror` 看偏离规模（>50 行说明历史代码不统一，本次只格式化改动区间）。
2. **定改动类型**：新文件 → 走骨架（include guard、include 顺序、static 原型、`(void)` 参数）；改函数 → 先看现有出口风格（`goto out` 还是多 return），**跟随**而不是顺手改造。
3. **写主路径前先写失败路径**：每个可能失败的调用（malloc/open/socket/read/write/send/recv/pthread\_*）先落失败分支，再写正常流；统一 `goto out` 逆序释放。
4. **逐条过规范**：布局与命名查 `references/style.md`（S1–S13）；指针/整数/资源/未定义行为查 `references/safety.md`（A1–A31）；症状眼熟先翻 `references/pitfalls.md` 的 36 条。
5. **自审**：按 `references/review-checklist.md` 30 项标 ✅/❌/N/A；每个 ❌ 要么改，要么在回复里写"为什么可以不改"。
6. **编译**：`-Wall -Wextra -Werror` 加 profile 里的额外开关；把命令与结果原样贴出，0 warning 才算过。
7. **收口**：格式改动与逻辑改动**分成两个 diff**；本次踩到新坑 → 转 `experience-capture`（单条经验）而非塞进本 Skill。

## 质量闸门

- [ ] `-Wall -Wextra -Werror` 下 0 warning；无隐式声明；无 `char *` 与 `void *` 隐式互转
- [ ] 所有可能失败的调用都有失败分支；每条 return/goto 路径上资源都已释放（fd、内存、锁、线程）
- [ ] 无 `strcpy/strcat/sprintf/gets/alloca`；`snprintf` 的返回值按"意图长度"判断截断
- [ ] 无魔术数字：超时、长度、重试次数、端口、协议号全部具名
- [ ] 日志走封装宏 `dbg_printf`（无裸 `printf/fprintf`），格式串为字面量
- [ ] 所有 `switch` 有 `default`；无 `break` 的 `case` 已写 `/* fall through */`
- [ ] 协议/持久化/跨进程结构体只用定长类型（`uint32_t` 等），无裸 `int/long`，无 `size_t` 上线
- [ ] 新函数原则上 ≤ 150 行；超 150 行已在回复中给出「单一输出 / 目的内聚 / 编排同层」三问结论（编排类可放行）
- [ ] 头文件自足（单独 `#include` 能编过）、有 guard、无变量定义
- [ ] 公共接口有 Doxygen 英文注释，NULL 契约 / 所有权 / 调用上下文 / 错误码齐全
- [ ] 缩进全为 Tab；续行是「Tab 到层 + 空格对齐」，无行首空格缩进
- [ ] 格式 diff 未与逻辑 diff 混在一起

## 输出格式

```
改动：<文件>:<行> — <一句话说明>
命中规则：<S 编号 / A 编号，最多 5 条>
自审：✅ n / ❌ m（逐条列 ❌ 与处理方式）
编译：<完整命令> → 0 warning（或贴关键输出）
待确认：<需要用户拍板的风格分歧，没有就写"无">
```

## 反面清单

- ❌ 没读 `profile.md` 就套"通用 C 风格"，tab 与空格混在同一文件
- ❌ 一个 diff 里既改缩进又改逻辑 —— reviewer 只能看到噪声，真正的 bug 被淹没
- ❌ 为"过 MISRA"写出绕来绕去、无人看得懂的代码：本规范是**裁剪版**，允许偏差，但偏差必须记录
- ❌ 顺手把相邻函数的风格一起改了（范围蔓延）
- ❌ 用 `assert` 校验外部输入（NDEBUG 下直接消失）
- ❌ 只说"符合规范"，却指不出具体文件名与条目编号

## 用例

**成功用例**：用户说"给 `sock_session` 加个空闲超时"。→ 先读 `profile.md` 取时间基准（`CLOCK_MONOTONIC`，毫秒）；改结构体加 `last_rx_ms`（定长 `uint64_t`）；失败路径先写（`clock_gettime` 返回值检查）；自审清单跑 30 项；编译 `gcc -Wall -Wextra -Werror`；输出含 S/A 编号与编译证据。

**边界用例**：用户说"把这段 2000 行的老代码整个重排成内核风格"。→ 不触发本 Skill 的"逐条执行"，而是回一句：这是**独立的格式化变更**，应单独提交、用 `clang-format` 一次成型，不与功能改动混合；先确认是否有 `.clang-format`，没有就先定基线（`profile.md` 的缩进/行宽），再决定是否值得引入。
