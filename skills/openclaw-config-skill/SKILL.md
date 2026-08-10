---
name: openclaw-config-skill
description: OpenClaw 配置管理技能。当用户需要：(1) 创建新 Agent 并配置工作区，(2) 为 Feishu 等渠道添加多账号，(3) 设置 Agent 路由绑定，(4) 修改模型/工具/网关配置时使用。提供备份→修改→验证→重启的标准流程，确保配置安全。
---

# OpenClaw 配置管理

## 快速开始

**常见场景：**
- "创建一个 operator Agent" → 加载 [agent-create.md](references/agent-create.md)
- "给 Feishu 添加新账号" → 加载 [feishu-channel.md](references/feishu-channel.md)
- "绑定 Agent 到渠道" → 加载 [agent-binding.md](references/agent-binding.md)

**完整流程：** 备份 → 执行场景步骤 → 验证 → 重启

---

## 场景导航

| 场景 | 参考文档 | 触发关键词 |
|------|----------|-----------|
| 创建新 Agent | [references/agent-create.md](references/agent-create.md) | "创建 Agent"、"新增 agent"、"添加 agent" |
| Feishu 渠道配置 | [references/feishu-channel.md](references/feishu-channel.md) | "Feishu 配置"、"飞书账号"、"飞书渠道" |
| 路由绑定 | [references/agent-binding.md](references/agent-binding.md) | "绑定"、"routing"、"binding"、"路由" |
| 命令参考 | [references/commands.md](references/commands.md) | "命令"、"CLI"、"帮助" |

---

## 标准流程（所有场景通用）

### 阶段 1：准备
1. **确认需求** - 与用户确认具体配置参数
2. **备份配置** - `./scripts/backup-config.sh`（自动保留最近 5 个备份）

### 阶段 2：执行
根据场景加载对应 reference，执行特定配置步骤。

### 阶段 3：验证
```bash
openclaw doctor --non-interactive
```
**通过** → 继续阶段 4  
**失败** → 见 [故障处理](#故障处理)

### 阶段 4：生效
```bash
openclaw gateway restart
```

---

## 故障处理

### 验证失败
1. **自动修复**：`openclaw doctor --fix`
2. **恢复备份**：`cp ~/.openclaw/openclaw_backups/openclaw.json.<timestamp> ~/.openclaw/openclaw.json`
3. **人工检查**：用户手动编辑配置

### Gateway 重启失败
1. 检查端口：`lsof -i :18789`
2. 查看日志：`/tmp/openclaw/openclaw.log`
3. 手动启停：`openclaw gateway stop` → `start`

---

## 配置路径

- 配置文件：`~/.openclaw/openclaw.json`
- 备份目录：`~/.openclaw/openclaw_backups/`
- Agent 目录：`~/.openclaw/agents/<agent-id>/`
- 日志文件：`/tmp/openclaw/openclaw.log`
