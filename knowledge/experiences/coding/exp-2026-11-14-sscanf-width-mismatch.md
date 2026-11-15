---
id: exp-2026-11-14-sscanf-width-mismatch
date: 2026-11-14
category: coding/parsing
domain: coding
problem_type: bug
trigger: "用 sscanf/scanf 的 %x/%u/%d 解析，同时把结果写进 char 或 short 变量"
symptom: "按 4 字节写入，踩坏相邻栈变量；可能立刻崩溃，也可能静默改掉别的变量导致后续逻辑错乱；ASan 报 stack-buffer-overflow，不开 sanitizer 时很难定位"
root_cause: "%x/%u/%d 对应的实参类型是 unsigned int*/int*，与 char*/short* 宽度不匹配；C 标准对该不匹配是未定义行为，编译器不会报错"
fix: "先解析到 unsigned int，做范围检查后再窄化；或使用长度修饰 %hhu/%hx/%hu；优先 strtoul/strtol + endptr + errno 做完整校验"
prevention: "scanf 家族的格式符必须与目标变量宽度严格匹配：char/short 用 hh/h 长度修饰，或先经临时变量转换。"
tags: [c, sscanf, format-string, stack-corruption]
confidence: medium
related: []
---

## 现象

解析函数返回成功，值也"看起来对"，但相邻变量被改成异常值；或崩溃发生在解析函数返回之后，与解析代码毫无关系。

## 机制

`sscanf(str, "%x", &c)` 中 `c` 是 `char`：格式化函数按 `unsigned int *` 解释这个地址并写入 4 字节，越界 3 字节。编译器不做跨函数类型校验，`-Wformat` 也管不到可变参数的这种误用（部分编译器能查 `scanf` 但默认不开）。

## 沉淀规则

> scanf 家族的格式符必须与目标变量宽度严格匹配：char/short 用 hh/h 长度修饰，或先经临时变量转换。

来源：用户 2026-11-14 口述。本条为机制描述，未附现场日志；confidence=medium。
