---
name: experience-capture
description: 把一个真实踩坑沉淀成结构化经验条目（exp-*）：症状、根因、修法、一句可执行 prevention；强制脱敏与查重合并。适用"报错了""踩坑""又遇到""排查半天"。
whenToUse: 一次排查超过 10 分钟、同一类报错出现第 2 次、修复了一个非显然的 bug、或用户说"记一下这个坑"。
---

# experience-capture — 经验捕获

## 触发条件

满足任一即执行：排查 >10 分钟；同类报错第 2 次出现；非显然的根因（表象与根因不同层）。
**不触发**：一眼可见的拼写错误、读文档即可解决的用法问题（那属于知识，不是经验）。

## 输入

- 报错原文或异常现象（可脱敏）
- 排查路径（试过什么、排除了什么）
- 真正的根因（不是"重启就好了"）
- 修复动作（最小可复现）

## 步骤

1. **查重**：`python .dsh/tools/kb.py search "<报错关键词>" --type experience`。
   - 命中同根因 → 在旧条目加 `## 复发记录`（日期 + 变体），打 tag 复用，不新建；
   - 同一 bug 不同根因 → 新建，并在 `related` 里互链。
2. **判定分类**：`domain` ∈ `coding|debugging|architecture|process`（主，落目录）；`problem_type` ∈ `bug|performance|tooling|process|knowledge`（副，见 dec-2026-11-07-g1-experience-taxonomy）。
3. **建骨架**：`python .dsh/tools/kb.py new experience --title "<症状一句话>" --slug <kebab-case> --domain <domain>`。
4. **写 front-matter 全部必填字段**：`trigger` `symptom` `root_cause` `fix` `prevention` `tags` `confidence`。
5. **脱敏检查**（G5，逐条过）：
   - [ ] 无 token / 密码 / 私钥 / Cookie
   - [ ] 无内部域名、内网 IP、真实库名表名
   - [ ] 无完整文件或整段业务代码（只留文件类型 + 关键签名）
   - [ ] 报错里的绝对路径已替换为 `<project>/...`
6. **写正文**：`## 现象`（报错原文，脱敏后）、`## 排查过程`（编号，写"排除了什么"）、`## 沉淀规则`（引用 prevention 原句）。
7. **校验入库**：`python .dsh/tools/kb.py validate` → `python .dsh/tools/kb.py index`。

## prevention 的写法（本 Skill 的核心）

一句可执行规则 = **触发条件 + 动作**，且能贴进检查清单：

- ✅ 「Windows 上用 pwsh 调 python 打印中文前，先 `$env:PYTHONUTF8=1`，否则 stdout 走 GBK 直接崩。」
- ✅ 「读 asar 内文件偏移时，先算 data section 起点，header 里的 offset 不是绝对偏移。」
- ❌ 「注意编码问题。」
- ❌ 「下次小心点。」

写不出这句 → **拒绝入库**，改为在任务卡里记一行 TODO，等根因明确再回来。

## 质量闸门

- [ ] `prevention` 是「条件 + 动作」，不是形容词
- [ ] `root_cause` 与 `symptom` 不在同一层（否则只是复述现象）
- [ ] 至少一条「排除了什么」，避免下次重走弯路
- [ ] 脱敏四项全过
- [ ] `kb.py validate` 零 error

## 输出格式

```
经验已落库：<相对路径>
ID：exp-YYYY-MM-DD-slug · domain: <d> · problem_type: <t> · confidence: <c>
规则：<prevention 原句>
复发风险：<什么情况下会再遇到>
```

## 反面清单

- ❌ 写成流水账（"先试了 A，又试了 B，最后好了"）——只留能复用的因果链。
- ❌ 根因写"环境问题"——必须落到具体机制（编码、路径、版本、权限）。
- ❌ 同一根因开三条——先查重再写。
- ❌ 把公司代码整段贴进 `## 现象`——G5 直接拒收。
