---
name: technical-analysis
description: 对股票K线数据进行技术分析，计算MA/MACD/RSI等指标，判断趋势和买卖信号。触发场景：(1) "分析一下茅台的技术面" (2) "看看这只股票能不能买" (3) "技术分析 600519" (4) 需要判断股票趋势、买卖点时使用。需要先用 data-collect 获取数据
---

# 技术分析

基于 K 线数据进行完整技术分析，输出趋势判断和买卖信号。

## 执行

```bash
# 完整流程：收集数据 → 技术分析
python data-collect/scripts/collect_stock_data.py 600519 | python scripts/analyze.py

# 或分步执行
python data-collect/scripts/collect_stock_data.py 600519 > stock.json
cat stock.json | python scripts/analyze.py
```

## 核心交易理念

1. **严进策略** - 乖离率 > 5% 坚决不买
2. **趋势交易** - MA5 > MA10 > MA20 多头排列
3. **买点偏好** - 缩量回踩 MA5/MA10 支撑

## 输出

```json
{
  "trend": {"status": "多头排列", "strength": 75, "is_bullish": true},
  "bias": {"ma5": 0.30, "status": "安全"},
  "macd": {"status": "GOLDEN_CROSS", "signal": "金叉，趋势向上"},
  "volume": {"status": "SHRINK_VOLUME_DOWN", "trend": "缩量回调"},
  "signal": {"action": "买入", "score": 72, "reasons": [...], "risks": [...]}
}
```

## 评分标准

| 分数 | 信号 |
|------|------|
| 75+ | 强烈买入 |
| 60-74 | 买入 |
| 45-59 | 持有 |
| 30-44 | 观望 |
| <30 | 卖出 |

详细指标说明见 [references/indicators.md](references/indicators.md)
