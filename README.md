# Qing Skills

AI 工作流 Codex Skills 集合。

## Skills

| Skill | 描述 |
|-------|------|
| [track-ai-plans](skills/track-ai-plans) | 在 Git 仓库中创建、执行、验证并通过自动安装的只读仪表盘跟踪 AI 工作计划 |

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
$track-ai-plans 创建或继续当前的 Git 工作计划
```

### 审查门禁

`track-ai-plans` 将计划制定、实施和审查分开：具名 subagent 创建草案，另一名 subagent 使用 `review-plan` 审查通过后，用户才能激活计划。每个阶段的所有任务完成后，必须由未参与该阶段实施的 subagent 使用 `review-phase` 审查通过，下一阶段才会解除阻塞。失败的审查需要先处理并重新审查。

```bash
# 独立 subagent 审查草案；planner 和 reviewer 必须不同
python3 scripts/planctl.py --root ROOT review-plan \
  --plan my-plan --result pass --evidence "范围、依赖与验证方式完整" \
  --actor plan-reviewer --actor-type agent

# 阶段全部任务完成后，由非实施者审查该阶段
python3 scripts/planctl.py --root ROOT review-phase \
  --phase phase-1 --result pass --evidence "实现、测试和计划文件均已核对" \
  --actor phase-reviewer --actor-type agent
```

审查记录、阻塞原因和下一步会写入计划状态，并显示在只读仪表盘中。

## 依赖

- Git
- Python 3

## License

MIT
