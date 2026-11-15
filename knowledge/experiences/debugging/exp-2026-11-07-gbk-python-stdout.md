---
id: exp-2026-11-07-gbk-python-stdout
date: 2026-11-07
category: debugging/windows-encoding
domain: debugging
problem_type: tooling
trigger: "在 pwsh 中用 -c 调用 python 并 print 中日韩字符"
symptom: "UnicodeEncodeError: 'gbk' codec can't encode character '\\U0001f9f1': illegal multibyte sequence，进程 exit 1，输出为空"
root_cause: "PowerShell 重定向子进程 stdout 时，Python 用 locale 编码(cp936/GBK)编码文本；字符不在 GBK 码表内即抛错，与源文件编码无关"
fix: "调用前设 $env:PYTHONIOENCODING='utf-8' 与 $env:PYTHONUTF8='1'；脚本内再加 sys.stdout.reconfigure(encoding='utf-8', errors='replace')"
prevention: "Windows 上任何「pwsh 调 python 并输出中文」的命令，先设 PYTHONUTF8=1 再执行，否则直接崩。"
tags: [windows, python, encoding, tooling]
confidence: high
related: [exp-2026-11-07-asar-offset-relative]
---

## 现象

在 PowerShell 里 `python -c "...print(中文/emoji)..."` 读 xlsx 时：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f9f1' in position 12
[exit code: 1]
```

前几行已打印出来的表头还是乱码（`�� ÿ�ս���`），后面的内容整个丢失。

## 排查过程

1. 先怀疑文件本身编码 → 用 `-Encoding Byte` 看头部是 `50 4B 03 04`（正常 xlsx/zip 头），排除文件损坏。
2. 再怀疑 openpyxl 读错 → 改成写 UTF-8 文本文件再读，内容完全正确，排除数据问题。
3. 定位到 `print()` 这一层：被重定向的 stdout 走 locale 编码，而 locale 是 cp936。
4. 设 `PYTHONUTF8=1` 后同一命令直接成功。

## 沉淀规则

> Windows 上任何「pwsh 调 python 并输出中文」的命令，先设 `PYTHONUTF8=1` 再执行，否则直接崩。

配套做法：长期脚本在 `main` 前 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，这样用户不设环境变量也不会炸。
