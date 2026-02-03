---
name: technical-analysis
description: 对股票K线数据进行技术分析，计算MA/MACD/RSI/KDJ等指标，判断趋势和买卖信号。触发场景：(1) "分析一下茅台的技术面" (2) "看看这只股票能不能买" (3) "技术分析 600519" (4) 需要判断股票趋势、买卖点时使用。需要先用 data-collect 获取数据
---

# 技术分析

基于 K 线数据进行完整技术分析，输出趋势判断和买卖信号。

## 工作流

```
/data-collect 600519
       ↓
/technical-analysis <stock_data>
```

## 执行

```bash
cat stock_data.json | python scripts/analyze.py
```

## 核心交易理念

1. **严进策略** - 乖离率 > 5% 坚决不买
2. **趋势交易** - MA5 > MA10 > MA20 多头排列
3. **买点偏好** - 缩量回踩 MA5/MA10 支撑

## 分析维度

| 维度 | 权重 | 关键指标 |
|------|------|----------|
| 趋势 | 30分 | MA5/MA10/MA20 排列 |
| 乖离率 | 20分 | 现价与MA5偏离度 |
| 量能 | 15分 | 量比、缩量/放量 |
| MACD | 15分 | 金叉/死叉/零轴位置 |
| 支撑 | 10分 | MA支撑有效性 |
| RSI | 10分 | 超买/超卖状态 |

## 输出格式

```json
{
  "code": "600519",
  "name": "贵州茅台",
  "trend": {"status": "多头排列", "strength": 75, "is_bullish": true},
  "price": {"current": 1690, "ma5": 1685, "ma10": 1670, "ma20": 1650},
  "bias": {"ma5": 0.30, "status": "安全"},
  "macd": {"status": "GOLDEN_CROSS", "signal": "金叉，趋势向上"},
  "rsi": {"rsi12": 58.2, "status": "STRONG_BUY"},
  "volume": {"status": "SHRINK_VOLUME_DOWN", "trend": "缩量回调"},
  "signal": {"action": "买入", "score": 72, "reasons": [...], "risks": [...]}
}
```

## 评分标准

| 分数 | 信号 | 操作 |
|------|------|------|
| 75+ | 强烈买入 | 可积极介入 |
| 60-74 | 买入 | 轻仓试探 |
| 45-59 | 持有 | 观望等待 |
| 30-44 | 观望 | 不宜介入 |
| <30 | 卖出 | 考虑离场 |

详细指标说明见 [references/indicators.md](references/indicators.md)
