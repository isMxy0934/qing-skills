# Qing Skills

AI 工作流 Codex Skills 集合。

## Skills

| Skill | 描述 |
|-------|------|
| [track-ai-plans](skills/track-ai-plans) | 用可恢复计划、项目地图、变更证据和只读仪表盘追踪 Git 仓库中的长任务 |

## 安装

```bash
# 安装（跨平台，安装整个技能集）
npx skills add isMxy0934/qing-skills

# 安装单个 skill（任选其一）
npx skills add isMxy0934/qing-skills@track-ai-plans
npx skills add https://github.com/isMxy0934/qing-skills --skill track-ai-plans

# 检查更新
npx skills check

# 更新已安装 skills
npx skills update
```

## 使用

```
$track-ai-plans 发现、创建或继续当前的 Qing Plan
```

### 长任务与独立审查

计划保存在仓库的 `qing-plans/` 中，其他 agent 或另一台电脑可从 Git 恢复当前目标、下一步、修改原因和验证证据。`resume` 会主动发现未完成计划；暂停计划需要明确恢复，避免劫持新请求。

审查策略只有两种：普通任务使用 `none`，依靠测试和验证证据；长任务默认使用 `single`，由一个独立 agent 审查初始计划以及重大范围修订。阶段之间不设置额外审查门禁。

`PLANCTL` 始终指向 skill 自带的 `scripts/planctl.py`（具体路径随安装方式而不同）。仓库里只有计划数据和仪表盘，不会被写入任何脚本，因此首次创建计划前后、换机器前后，命令完全一致。

```bash
# 创建长任务；默认 review policy 为 single
python3 "$PLANCTL" --root ROOT create \
  --slug my-plan --name "跨 agent 的长任务" --goal "完成可恢复的长任务" \
  --actor planner-agent --actor-type agent

# 由独立 agent 审查当前计划 revision
python3 "$PLANCTL" --root ROOT review-plan \
  --plan my-plan --result pass --evidence "范围、依赖与验证方式完整" \
  --actor plan-reviewer --actor-type agent

# 新 agent 开始前主动发现当前工作
python3 "$PLANCTL" --root ROOT resume
```

仪表盘位于 `qing-plans/dashboard.html`，按模块展示计划文件、实际修改、修改原因、上下游关系、修订、问题与验证状态。项目地图由 agent 随计划逐步维护，不依赖语言特定的 AST 分析。skill 升级后如需刷新仪表盘：

```bash
python3 "$PLANCTL" --root ROOT install-dashboard
```

## 依赖

- Git
- Python 3

## License

MIT
