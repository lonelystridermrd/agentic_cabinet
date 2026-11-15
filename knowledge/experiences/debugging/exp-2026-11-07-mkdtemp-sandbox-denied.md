---
id: exp-2026-11-07-mkdtemp-sandbox-denied
date: 2026-11-07
category: debugging/windows-sandbox
domain: debugging
problem_type: tooling
trigger: "在 DSH Windows 沙箱内用 tempfile.mkdtemp 建临时目录，再往里创建子目录"
symptom: "PermissionError: [WinError 5] 拒绝访问: '<tmp>\\kb-selftest-xxx\\.dsh'，同一进程对刚创建目录无写权限"
root_cause: "mkdtemp 以 mode=0o700 创建目录；该目录在 DSH 沙箱下继承到受限 ACL，后续 CreateDirectory 被拒。用普通 os.makedirs/Path.mkdir 创建的目录没有此问题（已对照验证：同一路径改为显式 mkdir 后子目录创建成功）"
fix: "自检脚本改为「工作区内显式 mkdir + 进程号/序号」作为用例根；不再使用 mkdtemp"
prevention: "DSH Windows 沙箱内建临时工作目录时用显式 mkdir（或 pwsh New-Item），不要用 tempfile.mkdtemp；报 WinError 5 先换建目录方式，别急着怀疑权限配置。"
tags: [windows, sandbox, python, testing]
confidence: medium
related: [exp-2026-11-07-gbk-python-stdout]
---

## 现象

`.dsh/tools/selftest.py` 第一版用 `tempfile.mkdtemp(prefix="kb-selftest-", dir=scratch)` 建用例根，全部 15 个用例在 setUp 阶段炸掉：

```
PermissionError: [WinError 5] 拒绝访问。:
'C:\...\agentic_skills_deployment\.selftest-tmp\kb-selftest-eri2typr\.dsh'
```

先在系统 `%TEMP%` 里试，同样报 WinError 5；换到工作区内也一样。

## 排查过程

1. 怀疑沙箱不授予 tmp 写权限 → 改到工作区内 `.selftest-tmp`，仍失败。
2. 用 pwsh `New-Item` 在工作区建 `.dsh`/`.config`/`dsh` 全部成功 → 排除「目录名被保护」。
3. 用 python `os.makedirs('.selftest-tmp/pyprobe/.dsh')` 成功 → 排除「python 不能建嵌套目录」。
4. 关键对照：先 `os.makedirs(dir)` 再建子目录 → OK；`os.chmod(dir, 0o700)` 后再建子目录 → OK；唯独 `tempfile.mkdtemp` 产出的目录建子目录 → WinError 5。
5. 改为显式 mkdir 命名（`case-<pid>-<n>`）后 15 个用例全过。
6. 残留的 mkdtemp 目录事后连**列出与删除**都被拒（UnauthorizedAccessException），只能留在原地并进 `.gitignore`——这进一步说明它拿到的是受限 ACL，而不是普通目录。

## 沉淀规则

> DSH Windows 沙箱内建临时工作目录时用显式 mkdir（或 pwsh New-Item），不要用 tempfile.mkdtemp；报 WinError 5 先换建目录方式，别急着怀疑权限配置。

置信度标 medium：现象与替代方案可复现，但「mkdtemp 具体如何影响 ACL」未逐层验证（`diagnose-windows-sandbox-acl` 可进一步取证）。
