---
name: data-collect
description: 收集股票历史K线、实时行情、筹码分布数据，支持A股/港股/美股/ETF。当用户提及股票代码、获取行情数据、K线、实时报价、筹码分布、或询问茅台/AAPL等股票时使用
---

# 股票数据收集

收集指定股票的完整数据：历史K线、实时行情、筹码分布（仅A股）。

## 执行命令

```bash
python scripts/collect_stock_data.py <股票代码> [--days N] [--date YYYY-MM-DD]

# 示例
python scripts/collect_stock_data.py 600519                      # A股，60天
python scripts/collect_stock_data.py 000001 --days 90            # 指定90天
python scripts/collect_stock_data.py AAPL --days 30              # 美股30天
```

**参数说明**：
- `--days`：获取天数（默认60天）
- `--date`：保存文件的日期标识（默认今天，不影响数据时间范围）

## 市场支持

自动识别市场类型：
- **A股**：6位数字（600519, 000001）
- **港股**：5位数字（00700, 09988）
- **美股**：字母代码（AAPL, MSFT）
- **ETF**：51/52/56/58开头（512880）

详见 [markets.md](references/markets.md)

## 输出结构

```
output/<股票代码>/<日期>/data.json
```

输出包含：
- `klines`：历史K线（日期、开高低收、成交量额、涨跌幅）
- `realtime`：实时行情（价格、量比、换手率、市盈率等）
- `chip`：筹码分布（仅A股，获利比例、筹码集中度等）

完整字段说明见 [fields.md](references/fields.md)

## 错误处理

**A股数据源**：自动切换东方财富→新浪→腾讯，所有源失败才报错

**可选数据**：实时行情和筹码数据获取失败不影响K线输出（会警告）

**防封禁**：脚本自动在请求间随机休眠2-5秒

## 依赖安装

```bash
pip install akshare pandas
```
