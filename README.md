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
# 安装（跨平台，安装整个技能集）
npx skills add isMxy0934/qing-skills

# 安装单个 skill（任选其一）
npx skills add isMxy0934/qing-skills@data-collect
npx skills add https://github.com/isMxy0934/qing-skills --skill data-collect

# 检查更新
npx skills check

# 更新已安装 skills
npx skills update
```

## 使用流程

```
/data-collect 600519           # 1. 收集数据
/technical-analysis <data>     # 2. 技术分析
/ai-decision <analysis>        # 3. 生成决策
```

## 依赖

```bash
pip install akshare tushare pandas
```

`data-collect` 默认使用 `akshare`，需要时可通过 `--provider tushare` 切换到 `tushare`（目前用于 A 股 K 线，需设置 `TUSHARE_TOKEN`）。

## License

MIT
