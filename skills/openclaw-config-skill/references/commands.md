# CLI 命令参考

## Agent 管理

```bash
openclaw agents list                    # 列出所有 Agent
openclaw agents add --id <id> ...       # 创建新 Agent
openclaw agents delete --id <id>        # 删除 Agent
openclaw agents set-identity --id <id>  # 设置身份
openclaw agents bind --agent-id <id> --channel <ch> --account-id <acc>
openclaw agents bindings                # 列出所有绑定
openclaw agents unbind --agent-id <id>  # 移除绑定
```

## 配置管理

```bash
openclaw config file                    # 显示配置文件路径
openclaw config get <dot.path>          # 获取配置值
openclaw config set <dot.path> <value>  # 设置配置值
openclaw config unset <dot.path>        # 删除配置值
openclaw config validate                # 验证配置
```

## 健康检查

```bash
openclaw doctor                         # 运行健康检查
openclaw doctor --non-interactive       # 非交互模式
openclaw doctor --fix                   # 自动修复
openclaw doctor --deep                  # 深度扫描
openclaw doctor --repair                # 修复并重启
```

## Gateway 管理

```bash
openclaw gateway status                 # 查看状态
openclaw gateway start                  # 启动
openclaw gateway stop                   # 停止
openclaw gateway restart                # 重启
```

## 脚本工具

```bash
./scripts/backup-config.sh              # 备份配置
./scripts/validate-and-restart.sh       # 验证并重启
```
