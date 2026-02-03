---
name: data-collect
description: 收集股票行情数据（K线、实时行情、筹码分布），支持 A股/港股/美股/ETF。当用户需要获取股票数据时使用。触发场景：(1) "获取茅台的数据" (2) "查一下 AAPL 行情" (3) "拉取 600519 K线" (4) "收集股票数据" (5) 任何涉及获取股票历史数据、实时报价的请求。注意：筹码分布仅 A股 支持
---

# 股票数据收集

收集指定股票的完整数据：历史K线、实时行情、筹码分布（仅A股）。

## 执行

```bash
python scripts/collect_stock_data.py <股票代码> [天数]

# 示例
python scripts/collect_stock_data.py 600519        # A股，默认60天
python scripts/collect_stock_data.py 000001 90     # A股，90天
python scripts/collect_stock_data.py 00700         # 港股
python scripts/collect_stock_data.py AAPL          # 美股
python scripts/collect_stock_data.py 512880        # ETF
```

## 市场识别规则

| 格式 | 市场 | 示例 |
|------|------|------|
| 6位数字 | A股 | 600519, 000001 |
| 5位数字 | 港股 | 00700, 09988 |
| 1-5位字母 | 美股 | AAPL, MSFT |
| 51/52/56/58/15/16/18开头 | ETF | 512880 |

## 输出格式

```json
{
  "code": "600519",
  "name": "贵州茅台",
  "market": "A股",
  "update_time": "2024-01-15 15:00:00",
  "klines": [{"date", "open", "high", "low", "close", "volume", "amount", "pct_chg"}],
  "realtime": {"price", "volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio", ...},
  "chip": {"profit_ratio", "avg_cost", "concentration_90", ...}
}
```

## 关键字段说明

| 字段 | 说明 | 用途 |
|------|------|------|
| volume_ratio | 量比 | >1.5放量, <0.7缩量 |
| turnover_rate | 换手率(%) | 活跃度指标 |
| profit_ratio | 获利比例 | 70-90%时警惕回吐 |
| concentration_90 | 90%筹码集中度 | <15%表示集中 |

## 注意事项

1. 每次请求间隔 2-5 秒防封禁
2. A股自动切换数据源（东方财富→新浪→腾讯）
3. 依赖：`pip install akshare pandas`
