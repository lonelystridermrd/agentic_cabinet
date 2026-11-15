---
id: exp-2026-11-07-frontmatter-empty-value-roundtrip
date: 2026-11-07
category: coding/python
domain: coding
problem_type: bug
trigger: "自写 front-matter 序列化把空字符串写成 `key:`，再被自己的解析器读回"
symptom: "新生成的决策骨架校验报「decision: 期望 string，实际 list」「alternatives: 元素数 0 < 1」——空值全变成了空列表"
root_cause: "解析器把 `key:` 后无内容的行当成「块列表开始」(data[key] = [])，而序列化端把空字符串也输出成 `key:`，两侧对同一个语法给了不同语义"
fix: "序列化端：空字符串输出 `key: \"\"`，空列表输出 `key: []`；解析端保持 `key:` 为块列表头"
prevention: "自研序列化/解析成对出现时，先写 round-trip 用例（dump→parse 必须等价），否则空值、布尔、含引号三类必然漂移。"
tags: [python, parser, serialization, testing]
confidence: high
related: [exp-2026-11-07-yaml-quoted-list-items]
---

## 现象

`kb.py new decision --title ... --slug ...` 生成的骨架，立刻被 `kb.py validate` 判为不合法：

```
ERROR ...decision: 期望 string，实际 list
ERROR ...alternatives: 元素数 0 < 1
ERROR ...rationale: 期望 string，实际 list
```

而手工写的同样字段完全正常。

## 排查过程

1. 打开生成文件：`decision:` 后面是空的，`alternatives:` 后面也没有值。
2. 回看解析器：`rest.strip() == ""` 时执行 `data[key] = []`（为块列表预留），于是一律变列表。
3. 序列化端 `dump_frontmatter` 对空字符串直接 `f"{k}: {v}"`，正好命中上面的分支配。
4. 修：空字符串输出 `""`、空列表输出 `[]`；再加一条 round-trip 断言进 selftest。

## 沉淀规则

> 自研序列化/解析成对出现时，先写 round-trip 用例（dump→parse 必须等价），否则空值、布尔、含引号三类必然漂移。

补充：这条与 exp-2026-11-07-yaml-quoted-list-items 同源——**同一份数据的多条代码路径必须共用归一化函数**，否则每加一种值类型就多一处隐性分叉。
