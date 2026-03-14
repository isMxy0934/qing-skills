# Agent 创建流程

## 适用场景

- 创建新的独立 Agent
- 为不同用途隔离工作区（如 operator、researcher）
- 配置多 Agent 路由

---

## 步骤 1：确认参数

与用户确认以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--id` | Agent 唯一标识 | `operator` |
| `--name` | 显示名称 | `Operator` |
| `--workspace` | 工作区路径 | `/home/admin/.openclaw/workspace-operator` |
| `--agent-dir` | Agent 配置目录 | `/home/admin/.openclaw/agents/operator/agent` |
| `--identity-name` | 身份名称（可选） | `Operator` |
| `--identity-emoji` | 表情符号（可选） | `⚙️` |
| `--identity-theme` | 主题（可选） | `运维工程师` |

---

## 步骤 2：创建 Agent

```bash
openclaw agents add \
  --id <agent-id> \
  --name <agent-name> \
  --workspace <workspace-path> \
  --agent-dir <agent-dir-path>
```

**带身份配置：**
```bash
openclaw agents add \
  --id operator \
  --name Operator \
  --workspace /home/admin/.openclaw/workspace-operator \
  --agent-dir /home/admin/.openclaw/agents/operator/agent \
  --identity-name Operator \
  --identity-emoji "⚙️" \
  --identity-theme "运维工程师"
```

---

## 步骤 3：添加路由绑定

创建 Agent 后，需要添加路由绑定才能接收消息：

```bash
openclaw agents bind \
  --agent-id <agent-id> \
  --channel <channel-name> \
  --account-id <account-id>
```

**示例（Feishu operator 账号）：**
```bash
openclaw agents bind \
  --agent-id operator \
  --channel feishu \
  --account-id operator
```

---

## 步骤 4：验证

```bash
openclaw agents list       # 确认 Agent 已创建
openclaw agents bindings   # 确认绑定已添加
openclaw doctor --non-interactive
```

---



---

## 注意事项

1. **Agent ID 必须唯一**，不能与现有 Agent 重复
2. **Workspace 和 AgentDir 必须不同**，避免冲突
3. **必须先有渠道账号** 才能绑定（如 Feishu operator 账号需先在 channels.feishu.accounts 中配置）
4. **default Agent 只能有一个**，多个时第一个生效

---

## 下一步

验证通过后执行标准流程的 [阶段 4：生效](../SKILL.md#阶段 4 生效)
