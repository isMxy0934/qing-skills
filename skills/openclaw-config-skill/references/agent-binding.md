# 路由绑定配置流程

## 适用场景

- 将 Agent 绑定到特定渠道 + 账号
- 修改现有路由规则
- 配置多 Agent 多账号路由策略

---

## 核心概念

**Binding（绑定）** = Agent + 渠道 + 账号的映射关系

```
Agent "operator" + Feishu 渠道 + "operator"账号 = 一条 Binding
```

当用户通过 Feishu operator 账号发送消息时，消息会路由到 operator Agent 处理。

---

## 步骤 1：确认绑定参数

与用户确认以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `agent-id` | 目标 Agent ID | `operator` |
| `channel` | 渠道名称 | `feishu`、`telegram`、`discord` |
| `account-id` | 渠道账号 ID | `operator`、`default` |

---

## 步骤 2：添加绑定

```bash
openclaw agents bind \
  --agent-id <agent-id> \
  --channel <channel-name> \
  --account-id <account-id>
```

**示例：**
```bash
# operator Agent 接收 Feishu operator 账号的消息
openclaw agents bind \
  --agent-id operator \
  --channel feishu \
  --account-id operator

# main Agent 接收 Telegram default 账号的消息
openclaw agents bind \
  --agent-id main \
  --channel telegram \
  --account-id default
```

---

## 步骤 3：查看绑定

```bash
# 列出所有绑定
openclaw agents bindings
```

**输出示例：**
```
Bindings:
  - agentId: main
    match:
      channel: feishu
      accountId: default

  - agentId: operator
    match:
      channel: feishu
      accountId: operator
```

---

## 步骤 4：移除绑定

```bash
openclaw agents unbind \
  --agent-id <agent-id> \
  --channel <channel-name> \
  --account-id <account-id>
```

**示例：**
```bash
openclaw agents unbind \
  --agent-id operator \
  --channel feishu \
  --account-id operator
```

---

## 高级绑定配置

### 直接编辑配置文件

对于复杂场景（如群聊特定规则），可直接编辑 `openclaw.json`：

```json5
{
  "bindings": [
    {
      "agentId": "main",
      "match": {
        "channel": "feishu",
        "accountId": "default"
      }
    },
    {
      "agentId": "operator",
      "match": {
        "channel": "feishu",
        "accountId": "operator",
        "peer": {
          "kind": "group",
          "id": "oc_xxx"
        }
      }
    }
  ]
}
```

### 匹配规则优先级

1. `peer`（特定会话）
2. `guildId` / `teamId`（特定群组/团队）
3. `accountId`（特定账号）
4. `accountId: "*"`（渠道内所有账号）
5. 默认 Agent（无匹配时）

---



---

## 注意事项

1. **Agent 必须先存在** 才能创建绑定
2. **渠道账号必须先配置** 才能绑定
3. **一个账号只能绑定一个 Agent**（后绑定的会覆盖）
4. **default Agent 作为 fallback**，当无匹配时使用

---

## 验证

```bash
openclaw agents bindings          # 查看绑定
openclaw doctor --non-interactive # 验证配置
```
