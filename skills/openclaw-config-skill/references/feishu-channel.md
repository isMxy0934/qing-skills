# Feishu 渠道配置流程

## 适用场景

- 为 Feishu 渠道添加新账号（多 Bot 配置）
- 修改现有账号配置
- 配置不同 Bot 对应不同 Agent

---

## 步骤 1：确认账号信息

与用户确认以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `account-id` | 账号唯一标识 | `operator`、`researcher` |
| `appId` | 飞书应用 App ID | `cli_a921715ec678dbca` |
| `appSecret` | 飞书应用密钥 | `Dnld1MM4VztBdFjoxJ1todsErrgS8EG6` |
| `botName` | Bot 显示名称 | `Operator 机器人` |
| `dmPolicy` | DM 策略 | `open` / `pairing` / `allowlist` |
| `allowFrom` | 允许的用户列表 | `["*"]` 或用户 ID 列表 |

---

## 步骤 2：添加账号配置

### 方式 A：使用 CLI 命令

```bash
# 添加账号配置
openclaw config set channels.feishu.accounts.<account-id>.appId <app-id>
openclaw config set channels.feishu.accounts.<account-id>.appSecret <app-secret>
openclaw config set channels.feishu.accounts.<account-id>.botName <bot-name>
```

### 方式 B：直接编辑配置文件

编辑 `~/.openclaw/openclaw.json`：

```json5
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_a922a5f8c9b8dcce",
      "appSecret": "bgpxVRv20AUIRgq6L902Nc1BOYjT0JyH",
      "accounts": {
        "default": {},
        "operator": {
          "appId": "cli_a921715ec678dbca",
          "appSecret": "Dnld1MM4VztBdFjoxJ1todsErrgS8EG6",
          "botName": "Operator 机器人",
          "dmPolicy": "open",
          "allowFrom": ["*"]
        },
        "researcher": {
          "appId": "cli_a9255dd7e2f91bdf",
          "appSecret": "Mk6RGREffMnQSK6wpdyHCb61gWsJVuPD",
          "botName": "Researcher 机器人",
          "dmPolicy": "open",
          "allowFrom": ["*"]
        }
      }
    }
  }
}
```

---

## 步骤 3：配置路由绑定

账号配置完成后，需要添加路由绑定：

```bash
openclaw agents bind \
  --agent-id <agent-id> \
  --channel feishu \
  --account-id <account-id>
```

**示例：**
```bash
# operator 账号 → operator Agent
openclaw agents bind --agent-id operator --channel feishu --account-id operator

# researcher 账号 → main Agent
openclaw agents bind --agent-id main --channel feishu --account-id researcher
```

---

## 步骤 4：验证配置

```bash
# 查看 Feishu 渠道配置
openclaw config get channels.feishu

# 查看账号列表
openclaw config get channels.feishu.accounts

# 验证配置
openclaw doctor --non-interactive
```

---



---

## 注意事项

1. **每个账号需要独立的飞书应用**（App ID + App Secret）
2. **账号 ID 必须唯一**，不能与现有账号重复
3. **必须先配置账号** 才能创建对应的路由绑定
4. **default 账号必须存在**，作为 fallback
