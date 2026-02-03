#!/usr/bin/env python3
"""
股票数据收集脚本
支持 A股/港股/美股/ETF

用法:
    python collect_stock_data.py <股票代码> [天数]

示例:
    python collect_stock_data.py 600519        # A股：贵州茅台，默认60天
    python collect_stock_data.py 000001 90     # A股：平安银行，90天
    python collect_stock_data.py 00700         # 港股：腾讯
    python collect_stock_data.py AAPL          # 美股：苹果
    python collect_stock_data.py 512880        # ETF：证券ETF
"""

import re
import random
import time
import json
import sys
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd


# === 防封禁策略 ===
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0',
]

_cache = {'data': None, 'timestamp': 0, 'ttl': 1200}  # 20分钟缓存


def random_sleep(min_sec: float = 2.0, max_sec: float = 5.0):
    """随机休眠，防止请求过快"""
    time.sleep(random.uniform(min_sec, max_sec))


def get_random_ua() -> str:
    """获取随机 User-Agent"""
    return random.choice(USER_AGENTS)


# === 市场识别 ===
def identify_market(code: str) -> str:
    """识别股票市场类型"""
    code = code.strip().upper()

    # 美股：1-5个大写字母，可能包含点（如 BRK.B）
    if re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code):
        return "美股"

    # 港股：5位数字 或 hk前缀
    if code.lower().startswith('hk'):
        return "港股"
    if code.isdigit() and len(code) == 5:
        return "港股"

    # ETF：特定前缀的6位数字
    etf_prefixes = ('51', '52', '56', '58', '15', '16', '18')
    if code.startswith(etf_prefixes) and len(code) == 6:
        return "ETF"

    # A股：6位数字
    if code.isdigit() and len(code) == 6:
        return "A股"

    return "未知"


# === 列名标准化 ===
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """统一列名"""
    column_map = {
        '日期': 'date', 'date': 'date',
        '开盘': 'open', 'open': 'open',
        '收盘': 'close', 'close': 'close',
        '最高': 'high', 'high': 'high',
        '最低': 'low', 'low': 'low',
        '成交量': 'volume', 'volume': 'volume',
        '成交额': 'amount', 'amount': 'amount',
        '涨跌幅': 'pct_chg', 'pct_chg': 'pct_chg',
    }
    df = df.rename(columns=column_map)

    # 计算涨跌幅（如果缺失）
    if 'pct_chg' not in df.columns and 'close' in df.columns:
        df['pct_chg'] = df['close'].pct_change() * 100
        df['pct_chg'] = df['pct_chg'].fillna(0)

    return df


# === A股数据（多数据源） ===
def _fetch_em(code: str, days: int) -> pd.DataFrame:
    """东方财富接口"""
    end = datetime.now()
    start = end - timedelta(days=days)

    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start.strftime('%Y%m%d'),
        end_date=end.strftime('%Y%m%d'),
        adjust="qfq"
    )
    return _normalize_columns(df)


def _fetch_sina(code: str, days: int) -> pd.DataFrame:
    """新浪财经接口"""
    end = datetime.now()
    start = end - timedelta(days=days)

    symbol = f"sh{code}" if code.startswith(('6', '5', '9')) else f"sz{code}"

    df = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date=start.strftime('%Y%m%d'),
        end_date=end.strftime('%Y%m%d'),
        adjust="qfq"
    )
    return _normalize_columns(df)


def _fetch_tencent(code: str, days: int) -> pd.DataFrame:
    """腾讯财经接口"""
    end = datetime.now()
    start = end - timedelta(days=days)

    symbol = f"sh{code}" if code.startswith(('6', '5', '9')) else f"sz{code}"

    df = ak.stock_zh_a_hist_tx(
        symbol=symbol,
        start_date=start.strftime('%Y%m%d'),
        end_date=end.strftime('%Y%m%d'),
        adjust="qfq"
    )
    return _normalize_columns(df)


def fetch_a_stock_kline(code: str, days: int = 60) -> pd.DataFrame:
    """获取 A股 K线数据，多数据源自动切换"""
    methods = [
        (_fetch_em, "东方财富"),
        (_fetch_sina, "新浪财经"),
        (_fetch_tencent, "腾讯财经"),
    ]

    for fetch_func, source_name in methods:
        try:
            random_sleep()
            df = fetch_func(code, days)
            if df is not None and not df.empty:
                print(f"[数据源] {source_name} 获取成功", file=sys.stderr)
                return df
        except Exception as e:
            print(f"[数据源] {source_name} 失败: {e}", file=sys.stderr)

    raise Exception("所有数据源均获取失败")


# === 港股数据 ===
def fetch_hk_stock_kline(code: str, days: int = 60) -> pd.DataFrame:
    """获取港股 K线数据"""
    code = code.lower().replace('hk', '').zfill(5)

    end = datetime.now()
    start = end - timedelta(days=days)

    random_sleep()
    df = ak.stock_hk_hist(
        symbol=code,
        period="daily",
        start_date=start.strftime('%Y%m%d'),
        end_date=end.strftime('%Y%m%d'),
        adjust="qfq"
    )
    return _normalize_columns(df)


# === 美股数据 ===
def fetch_us_stock_kline(code: str, days: int = 60) -> pd.DataFrame:
    """获取美股 K线数据"""
    code = code.strip().upper()
    end = datetime.now()
    start = end - timedelta(days=days)

    random_sleep()
    df = ak.stock_us_daily(symbol=code, adjust="qfq")

    df['date'] = pd.to_datetime(df['date'])
    df = df[(df['date'] >= start) & (df['date'] <= end)]
    df = _normalize_columns(df)

    if 'amount' not in df.columns:
        df['amount'] = df['volume'] * df['close']

    return df


# === ETF数据 ===
def fetch_etf_kline(code: str, days: int = 60) -> pd.DataFrame:
    """获取 ETF K线数据"""
    end = datetime.now()
    start = end - timedelta(days=days)

    random_sleep()
    df = ak.fund_etf_hist_em(
        symbol=code,
        period="daily",
        start_date=start.strftime('%Y%m%d'),
        end_date=end.strftime('%Y%m%d'),
        adjust="qfq"
    )
    return _normalize_columns(df)


# === 实时行情 ===
def fetch_realtime_quote(code: str, market: str) -> dict:
    """获取实时行情"""
    if market == "美股":
        return None

    random_sleep()

    if market == "港股":
        df = ak.stock_hk_spot_em()
        code = code.lower().replace('hk', '').zfill(5)
    elif market == "ETF":
        df = ak.fund_etf_spot_em()
    else:
        df = ak.stock_zh_a_spot_em()

    row = df[df['代码'] == code]
    if row.empty:
        return None

    row = row.iloc[0]

    def safe_float(val):
        try:
            return float(val) if val and str(val) not in ['', '-', 'nan'] else None
        except:
            return None

    return {
        'name': row.get('名称', ''),
        'price': safe_float(row.get('最新价')),
        'change_pct': safe_float(row.get('涨跌幅')),
        'change': safe_float(row.get('涨跌额')),
        'open': safe_float(row.get('今开')),
        'high': safe_float(row.get('最高')),
        'low': safe_float(row.get('最低')),
        'volume': safe_float(row.get('成交量')),
        'amount': safe_float(row.get('成交额')),
        'volume_ratio': safe_float(row.get('量比')),
        'turnover_rate': safe_float(row.get('换手率')),
        'pe_ratio': safe_float(row.get('市盈率-动态')),
        'pb_ratio': safe_float(row.get('市净率')),
        'total_mv': safe_float(row.get('总市值')),
        'circ_mv': safe_float(row.get('流通市值')),
        'amplitude': safe_float(row.get('振幅')),
        'high_52w': safe_float(row.get('52周最高')),
        'low_52w': safe_float(row.get('52周最低')),
        'change_60d': safe_float(row.get('60日涨跌幅')),
    }


# === 筹码分布（A股专属） ===
def fetch_chip_distribution(code: str) -> dict:
    """获取筹码分布数据"""
    random_sleep()

    try:
        df = ak.stock_cyq_em(symbol=code)
        if df.empty:
            return None

        latest = df.iloc[-1]

        def safe_float(val):
            try:
                return float(val) if val and str(val) not in ['', '-', 'nan'] else None
            except:
                return None

        return {
            'date': str(latest.get('日期', '')),
            'profit_ratio': safe_float(latest.get('获利比例')),
            'avg_cost': safe_float(latest.get('平均成本')),
            'concentration_90': safe_float(latest.get('90集中度')),
            'concentration_70': safe_float(latest.get('70集中度')),
            'cost_90_low': safe_float(latest.get('90成本-低')),
            'cost_90_high': safe_float(latest.get('90成本-高')),
            'cost_70_low': safe_float(latest.get('70成本-低')),
            'cost_70_high': safe_float(latest.get('70成本-高')),
        }
    except Exception as e:
        print(f"获取筹码数据失败: {e}", file=sys.stderr)
        return None


# === 统一入口 ===
def collect_stock_data(code: str, days: int = 60) -> dict:
    """统一数据收集入口"""
    market = identify_market(code)

    # 获取 K线数据
    if market == "美股":
        klines_df = fetch_us_stock_kline(code, days)
    elif market == "港股":
        klines_df = fetch_hk_stock_kline(code, days)
    elif market == "ETF":
        klines_df = fetch_etf_kline(code, days)
    else:
        klines_df = fetch_a_stock_kline(code, days)

    # 转换为列表格式
    klines = []
    for _, row in klines_df.iterrows():
        klines.append({
            'date': str(row['date']),
            'open': round(float(row['open']), 2),
            'high': round(float(row['high']), 2),
            'low': round(float(row['low']), 2),
            'close': round(float(row['close']), 2),
            'volume': int(row['volume']),
            'amount': float(row.get('amount', 0)),
            'pct_chg': round(float(row.get('pct_chg', 0)), 2),
        })

    # 获取实时行情
    realtime = fetch_realtime_quote(code, market)

    # 获取筹码分布（仅 A股）
    chip = None
    if market == "A股":
        chip = fetch_chip_distribution(code)

    return {
        'code': code,
        'name': realtime.get('name', code) if realtime else code,
        'market': market,
        'source': 'akshare',
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'klines': klines,
        'realtime': realtime,
        'chip': chip,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python collect_stock_data.py <股票代码> [天数]")
        print("示例: python collect_stock_data.py 600519 60")
        sys.exit(1)

    code = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    result = collect_stock_data(code, days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
