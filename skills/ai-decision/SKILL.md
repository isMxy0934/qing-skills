---
name: ai-decision
description: 基于技术分析结果生成投资决策仪表盘，包括核心结论、精确价位、检查清单和风险警报。触发场景：(1) "给我投资建议" (2) "这只股票该怎么操作" (3) "生成决策报告" (4) 需要综合决策建议时使用。需要先用 technical-analysis 获取分析结果
---

# AI 决策仪表盘

基于技术分析结果，生成完整的投资决策建议。

## 执行

```bash
# 完整流程：收集 → 分析 → 决策
python data-collect/scripts/collect_stock_data.py 600519 \
  | python technical-analysis/scripts/analyze.py \
  | python scripts/decision.py

# 带舆情输入
python data-collect/scripts/collect_stock_data.py 600519 \
  | python technical-analysis/scripts/analyze.py \
  | python scripts/decision.py --news "公司发布利好公告"
```

## 输出内容

1. **核心结论** - 一句话结论 + 分持仓建议
2. **精确价位** - 理想买入/次优买入/止损/目标价
3. **检查清单** - 6项关键条件逐一检查
4. **舆情情报** - 风险警报 + 利好催化

## 输出格式

```json
{
  "core_conclusion": {
    "one_sentence": "多头趋势良好但乖离率偏高，等待回踩MA5",
    "signal_type": "HOLD",
    "position_advice": {"no_position": "...", "has_position": "..."}
  },
  "price_levels": {
    "ideal_buy": 1670.00,
    "stop_loss": 1640.00,
    "take_profit": 1750.00,
    "risk_reward_ratio": 2.67
  },
  "checklist": [
    "[YES] 多头排列：MA5>MA10>MA20 满足",
    "[YES] 乖离率<5%：当前0.3%",
    "[YES] 量能配合：缩量回调",
    "[YES] 无重大利空",
    "[WARN] 筹码结构：获利盘85%",
    "[NO] 买点位置：当前价高于理想买点"
  ],
  "summary": {"action": "观望", "score": 72, "confidence": "中"}
}
```

## 信号类型

| 信号 | 含义 | 操作 |
|------|------|------|
| BUY | 买入信号 | 可建仓 |
| HOLD | 持有观望 | 等待更好时机 |
| SELL | 卖出信号 | 减仓/离场 |

详细交易规则见 [references/trading-rules.md](references/trading-rules.md)
