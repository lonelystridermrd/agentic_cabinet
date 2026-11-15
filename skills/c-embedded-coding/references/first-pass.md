# L0 · 首次生成硬护栏（13 条禁止）

> 触发：新建 `.c`/`.h` 文件。写完**一个文件**就检查，不通过不写下一个。
> 机械判定：`python .dsh/tools/style_check.py <file>`，输出必须贴进回复。

| # | 禁止 | 正确做法 |
|---|---|---|
| 1 | `typedef struct X X_t` | `struct X`，指针写 `struct X *` |
| 2 | `strcpy/strcat/sprintf/gets` | `snprintf` / `strlcpy`，判截断 |
| 3 | `alloca` | 堆或静态池 |
| 4 | 裸 `printf/fprintf` | 项目日志封装宏 |
| 5 | `switch` 无 `default` | 一律写 `default`；贯穿写 `/* fall through */` |
| 6 | 行宽 >120 | 断行，续行「Tab 到层 + 空格对齐」 |
| 7 | 空格缩进 | 一律 Tab |
| 8 | 头文件无 guard | `#ifndef X_H` / `#define` / `#endif` |
| 9 | 公共函数无 Doxygen | `@brief/@param/@return/@note`，含 NULL 契约 |
| 10 | `malloc/open/read/write/pthread_*` 返回值未判 | 每个失败分支先写 |
| 11 | 协议/持久化结构体用 `size_t`/`int` | 定长类型 `uint32_t` 等 |
| 12 | 资源获取后错误路径不释放 | 统一 `goto out` 逆序释放 |
| 13 | 函数无 Doxygen 头注释 | 每个函数（含 `static`）用 `/** @brief ... */`，有参数/返回值补 `@param`/`@return` |

## 生成后立即执行

```sh
python .dsh/tools/style_check.py path/to/file.c
```

- 输出以 `PASS` 开头 → 贴进回复，继续下一个文件。
- `FAIL` → 修到 PASS，**不得**继续写下一个文件。
- 全部写完再跑一次 `--all <dir>` 复核，防止中途手改引入回归。

## 自检话术（回复里必须有）

```
L0：<file> PASS（style_check 输出见上）
```
