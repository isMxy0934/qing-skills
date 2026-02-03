# Qing Skills

股票技术分析 Claude Code Skills 集合。

## Skills

| Skill | 描述 |
|-------|------|
| [data-collect](skills/data-collect) | 收集股票行情数据（K线、实时行情、筹码分布） |
| [technical-analysis](skills/technical-analysis) | 技术分析（已实现：MA/MACD/RSI；计划：KDJ） |
| [ai-decision](skills/ai-decision) | AI 投资决策仪表盘 |

## 安装

```bash
# 安装单个 skill
claude skill add https://github.com/isMxy0934/qing-skills/skills/data-collect
claude skill add https://github.com/isMxy0934/qing-skills/skills/technical-analysis
claude skill add https://github.com/isMxy0934/qing-skills/skills/ai-decision
```

## 使用流程

```
/data-collect 600519           # 1. 收集数据
/technical-analysis <data>     # 2. 技术分析
/ai-decision <analysis>        # 3. 生成决策
```

## 依赖

```bash
pip install akshare pandas
```

## License

MIT
