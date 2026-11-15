# 编译产物实测方法

> 为什么必须自测：他人的 benchmark 在别人的架构、编译选项、负载下得出，**不可比**。
> 自测是最强证据（A 级），也是唯一能回答"在我们目标平台上到底多大/多快"的方法。

## 一、产物体积

```sh
size build/app                       # text / data / bss 三段
bloaty build/app -d compileunits,symbols   # 定位体积大头
nm --size-sort -S build/app | tail -30     # 单个符号贡献
```

- **静态与动态分开测**；`strip` 与不 `strip` 分开记录。
- 额外做一次"只链接被评测组件 + 空 main"，隔离出库本身的增量（排除运行时库干扰）。
- 体积一律给绝对值（字节/KB）+ 相对值（vs 最小方案）。

## 二、运行时内存

```sh
/usr/bin/time -v ./app              # Maximum resident set size
valgrind --tool=massif ./app        # heap 峰值（ms_print 查看）
```

- 程序内可用 `getrusage(RUSAGE_SELF, &ru)` 的 `ru_maxrss`（Linux 单位 KB）。
- 测**稳定态峰值**，不是启动瞬间；跑 ≥30 次取中位数。
- RSS 受页缓存与工具本身影响：同一台机器、同一测量工具、同一输入。

## 三、启动时间

- `CLOCK_MONOTONIC` 在 main 入口打点，到"可对外服务"再打一次。
- ≥30 次取中位数与 P99；首次运行单独标注（页错误影响）。

## 四、依赖与编译成本

```sh
ldd build/app
readelf -d build/app
```

- 传递依赖：包管理器（apt/vcpkg/conan）依赖树。
- 源码规模：`cloc` 或 `wc -l`。
- 编译时间：`time make -j1`（必须单线程才可比；`-j` 会让结果失去意义）。

## 五、可比性六要素（缺一数据无效）

1. 架构（x86_64 / arm64 / mips32）
2. 编译器与版本（gcc 12.2 / clang 16）
3. 编译选项（`-O2` / `-Os` / `-flto` / `-DNDEBUG`）
4. libc（glibc / musl）与版本
5. 内核版本
6. 输入负载（包长、并发、数据量）

## 六、常见陷阱

- `-Os` 与 `-O2` 混比；LTO 开关不一致
- 静态链接与动态链接混比
- 只测空闲内存，不测峰值
- 用平均值代替 P99 / 最大值
- 在 x86 上测完直接推断 ARM（指令密度、cache 大小都不同）
- 测量工具自身的开销（valgrind 会放大内存与时间）
- 忽略 BSS（静态大数组不计入文件体积，但计入内存）

## 七、记录模板

| 方案 | 版本 | 架构 | 编译器 | 选项 | 链接 | 体积 | RSS | 启动 | 依赖数 | 编译时间 |
|---|---|---|---|---|---|---|---|---|---|---|
| A | x.y.z | arm64 | gcc 12.2 | -Os -DNDEBUG | static | 214KB | 1.8MB | 12ms | 0 | 41s |

附录写复现命令（可直接复制执行）与原始输出。
