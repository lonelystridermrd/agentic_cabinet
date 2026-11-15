<!-- 由 .dsh/tools/kb.py index 自动生成，禁止手改；改条目后重跑 kb.py index -->

# 经验索引

共 12 条 · 生成于 2026-11-16 00:05

分类维度：`domain`（领域，主）× `problem_type`（问题类型，副），见 dec-2026-11-07-g1-experience-taxonomy。

## coding（8）

| ID | 日期 | 标题 | 问题类型 | 置信度 | tags |
|---|---|---|---|---|---|
| [exp-2026-11-07-frontmatter-empty-value-roundtrip](exp-2026-11-07-frontmatter-empty-value-roundtrip.md) | 2026-11-07 | 自写 front-matter 序列化把空字符串写成 `key:`，再被自己的解析器读回 | bug | high | python, parser, serialization, testing |
| [exp-2026-11-07-yaml-quoted-list-items](exp-2026-11-07-yaml-quoted-list-items.md) | 2026-11-07 | 自写的极简 YAML front-matter 解析器遇到带引号的块列表项 | bug | high | python, parser, yaml, coding |
| [exp-2026-11-14-async-ownership-early-free](exp-2026-11-14-async-ownership-early-free.md) | 2026-11-14 | malloc 出的对象通过注册接口交给其它线程或全局框架后，调用方在注册成功时当场 free | bug | medium | c, memory, ownership, concurrency |
| [exp-2026-11-14-loop-alloc-partial-free](exp-2026-11-14-loop-alloc-partial-free.md) | 2026-11-14 | 循环里逐个 malloc，中途某次失败时只释放当前这一个条目就返回错误 | bug | medium | c, memory, error-path, rollback |
| [exp-2026-11-14-memcpy-one-sided-length-check](exp-2026-11-14-memcpy-one-sided-length-check.md) | 2026-11-14 | 调用 memcpy 时，长度 n 只对 src 或 dst 其中一侧做过容量校验 | bug | medium | c, memory, memcpy, bounds |
| [exp-2026-11-14-select-closed-fd](exp-2026-11-14-select-closed-fd.md) | 2026-11-14 | select 的 fd_set 里仍保留已经 close 掉的套接字 | bug | medium | c, socket, select, fd-lifecycle |
| [exp-2026-11-14-sscanf-width-mismatch](exp-2026-11-14-sscanf-width-mismatch.md) | 2026-11-14 | 用 sscanf/scanf 的 %x/%u/%d 解析，同时把结果写进 char 或 short 变量 | bug | medium | c, sscanf, format-string, stack-corruption |
| [exp-2026-11-14-uninit-stack-var](exp-2026-11-14-uninit-stack-var.md) | 2026-11-14 | 栈上的变量或结构体没有初始化，就传给其它进程（管道/共享内存/消息），或者直接自增 | bug | medium | c, uninitialized, stack, ipc |

## debugging（3）

| ID | 日期 | 标题 | 问题类型 | 置信度 | tags |
|---|---|---|---|---|---|
| [exp-2026-11-07-asar-offset-relative](exp-2026-11-07-asar-offset-relative.md) | 2026-11-07 | 想从 app.asar 里按 header 记录的 offset 直接读某个文件内容 | knowledge | high | asar, binary-format, electron, tooling |
| [exp-2026-11-07-gbk-python-stdout](exp-2026-11-07-gbk-python-stdout.md) | 2026-11-07 | 在 pwsh 中用 -c 调用 python 并 print 中日韩字符 | tooling | high | windows, python, encoding, tooling |
| [exp-2026-11-07-mkdtemp-sandbox-denied](exp-2026-11-07-mkdtemp-sandbox-denied.md) | 2026-11-07 | 在 DSH Windows 沙箱内用 tempfile.mkdtemp 建临时目录，再往里创建子目录 | tooling | medium | windows, sandbox, python, testing |

## process（1）

| ID | 日期 | 标题 | 问题类型 | 置信度 | tags |
|---|---|---|---|---|---|
| [exp-2026-11-07-template-dir-scanned](exp-2026-11-07-template-dir-scanned.md) | 2026-11-07 | 知识库模板文件放在被扫描的目录树内 | process | high | knowledge-base, scanning, tooling, process |

## 按问题类型

- **bug**（8）：`exp-2026-11-07-frontmatter-empty-value-roundtrip`、`exp-2026-11-07-yaml-quoted-list-items`、`exp-2026-11-14-async-ownership-early-free`、`exp-2026-11-14-loop-alloc-partial-free`、`exp-2026-11-14-memcpy-one-sided-length-check`、`exp-2026-11-14-select-closed-fd`、`exp-2026-11-14-sscanf-width-mismatch`、`exp-2026-11-14-uninit-stack-var`
- **knowledge**（1）：`exp-2026-11-07-asar-offset-relative`
- **process**（1）：`exp-2026-11-07-template-dir-scanned`
- **tooling**（2）：`exp-2026-11-07-gbk-python-stdout`、`exp-2026-11-07-mkdtemp-sandbox-denied`
