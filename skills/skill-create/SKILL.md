---
name: skill-create
description: >-
  Audits an Agent Skill directory against Cursor skill authoring conventions (frontmatter, description, structure, progressive disclosure, scripts, anti-patterns). Use when the user asks to review whether a skill is well-formed, 技能是否符合规范, 检查 SKILL 写法, skill compliance, or quality of skills like a-share-stock-picker.
---

# Skill 规范审查（Skill compliance audit）

## 何时使用

用户给出或未给出具体路径时，对某个技能目录做**结构 + 元数据 + 可维护性**审查，对照 Cursor 官方「Creating Skills」约定（与内置 create-skill 指南一致）。

默认：若用户用 `@` 指向某目录（例如 `skills/a-share-stock-picker/`），以该目录为审查目标；否则先确认路径再查。

## 审查步骤

1. **列目录**：确认存在根级 `SKILL.md`；记录 `references/`、`scripts/`、`agents/` 等子目录。
2. **读 frontmatter**（`SKILL.md` 顶部 `---` 块）：
   - `name`：存在、全小写、仅字母数字与连字符、≤64 字符。
   - `description`：非空、≤1024 字符、**第三人称**（避免「我/你可以…」）、同时写清 **做什么（WHAT）** 与 **何时用（WHEN）**、含可检索触发词。
3. **读正文体量**：`SKILL.md` 主体宜 **≤500 行**；过长应拆到 `references/*.md` 等（渐进式披露）。
4. **链接与引用**：从 `SKILL.md` 指向附属文件时，**一层深度** 即可（如 `references/foo.md`），避免深层嵌套才读得到的关键步骤。
5. **脚本**：若存在 `scripts/`，检查 `SKILL.md` 是否说明用途、调用方式、是否应**执行**还是仅作参考；路径用正斜杠。
6. **反模式扫描**：Windows 反斜杠路径、过多等价工具罗列无默认项、易过期硬编码日期（非示例）、术语前后不一致。
7. **仓库扩展项**（本仓常见）：`agents/openai.yaml` 等若存在，检查是否与 `SKILL.md` 的 `name`/能力描述一致、是否在正文中被提及（未提及则记为「可选元数据，建议在 SKILL 中加一句说明」）。

## 输出格式（必须）

用中文给出简明报告，固定小节：

1. **结论**：合规 / 基本合规需小改 / 需重点修订（一句话）。
2. **符合项**：条目列表。
3. **问题与建议**：分 **严重**（影响发现性、误用、安全）/ **一般**（可读性、重复、结构）。
4. **可选后续**：若要满分，优先做的 1–3 件事。

不替用户改稿，除非用户明确要求修改该技能。

## 快速自检清单（可内联勾选）

- [ ] `name` / `description` 符合字段规则
- [ ] `description` 含 WHAT + WHEN + 触发词
- [ ] `SKILL.md` 行数与拆分合理
- [ ] 引用一层深、附属文件可被按需阅读
- [ ] 脚本有说明、路径风格正确
- [ ] 无典型反模式
