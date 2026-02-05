#!/usr/bin/env python3
"""
股票数据收集脚本
支持 A股/港股/美股/ETF

用法:
    python collect_stock_data.py <股票代码> [--days N] [--provider akshare|tushare] --date YYYY-MM-DD

示例:
    python collect_stock_data.py 600519 --date 2025-01-01                     # A股，60天
    python collect_stock_data.py 000001 --days 90 --date 2025-01-01           # A股，90天
    python collect_stock_data.py 00700 --days 30 --date 2025-01-01            # 港股，30天
    python collect_stock_data.py AAPL --days 30 --date 2025-01-01             # 美股，30天
    python collect_stock_data.py 512880 --date 2025-01-01                     # ETF，60天
    python collect_stock_data.py 600519 --provider tushare --date 2025-01-01  # A股 tushare
    python collect_stock_data.py 600519 --date 2025-01-01   # 指定保存日期（必填）
"""

import re
import random
import time
import json
import sys
import os
from datetime import datetime, timedelta

import pandas as pd
import akshare as ak

try:
    import tushare as ts
except ImportError:
    ts = None

def random_sleep(min_sec: float = 2.0, max_sec: float = 5.0):
    """随机休眠，防止请求过快"""
    time.sleep(random.uniform(min_sec, max_sec))


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
        'trade_date': 'date',
        '开盘': 'open', 'open': 'open',
        '收盘': 'close', 'close': 'close',
        '最高': 'high', 'high': 'high',
        '最低': 'low', 'low': 'low',
        '成交量': 'volume', 'volume': 'volume',
        'vol': 'volume',
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


def fetch_a_stock_kline_akshare(code: str, days: int = 60) -> pd.DataFrame:
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


def _to_tushare_ts_code(code: str) -> str:
    """A股代码转换为 tushare ts_code"""
    if not code.isdigit() or len(code) != 6:
        raise ValueError("tushare 目前仅支持 6 位 A 股代码")
    suffix = "SH" if code.startswith(('5', '6', '9')) else "SZ"
    return f"{code}.{suffix}"


def fetch_a_stock_kline_tushare(code: str, days: int = 60) -> pd.DataFrame:
    """通过 tushare 获取 A股 K线数据"""
    if ts is None:
        raise ImportError("未安装 tushare，请先执行: pip install tushare")

    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise ValueError("缺少 TUSHARE_TOKEN 环境变量，无法使用 tushare 数据源")

    ts.set_token(token)
    ts_code = _to_tushare_ts_code(code)

    end = datetime.now()
    start = end - timedelta(days=days)
    random_sleep()
    df = ts.pro_bar(
        ts_code=ts_code,
        start_date=start.strftime('%Y%m%d'),
        end_date=end.strftime('%Y%m%d'),
        freq='D',
        adj='qfq'
    )
    if df is None or df.empty:
        raise Exception("tushare 返回空数据")

    df = _normalize_columns(df)
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
    df = df.sort_values('date').reset_index(drop=True)
    return df


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
def collect_stock_data(code: str, days: int = 60, provider: str = "akshare") -> dict:
    """统一数据收集入口"""
    provider = provider.strip().lower()
    if provider not in ("akshare", "tushare"):
        raise ValueError("provider 仅支持: akshare, tushare")

    market = identify_market(code)

    if market == "未知":
        raise ValueError(
            f"不支持的股票代码/市场: {code}。"
            "请检查代码格式，或参考 skills/data-collect/references/markets.md 的识别规则。"
        )

    # 获取 K线数据
    if provider == "tushare":
        if market != "A股":
            raise ValueError("tushare 目前仅支持 A 股 K 线，请改用 --provider akshare")
        klines_df = fetch_a_stock_kline_tushare(code, days)
    else:
        if market == "美股":
            klines_df = fetch_us_stock_kline(code, days)
        elif market == "港股":
            klines_df = fetch_hk_stock_kline(code, days)
        elif market == "ETF":
            klines_df = fetch_etf_kline(code, days)
        else:
            klines_df = fetch_a_stock_kline_akshare(code, days)

    # 转换为列表格式
    klines = []
    for _, row in klines_df.iterrows():
        # 安全转换函数
        def safe_float(val, default=0.0):
            try:
                return float(val) if pd.notna(val) else default
            except (ValueError, TypeError):
                return default
        
        def safe_int(val, default=0):
            try:
                return int(val) if pd.notna(val) else default
            except (ValueError, TypeError):
                return default
        
        # 标准化日期格式为 YYYY-MM-DD
        date_val = row['date']
        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val).split()[0]  # 去除可能的时间部分
        
        klines.append({
            'date': date_str,
            'open': round(safe_float(row['open']), 2),
            'high': round(safe_float(row['high']), 2),
            'low': round(safe_float(row['low']), 2),
            'close': round(safe_float(row['close']), 2),
            'volume': safe_int(row['volume']),
            'amount': safe_float(row.get('amount', 0)),
            'pct_chg': round(safe_float(row.get('pct_chg', 0)), 2),
        })

    # 获取实时行情（可选，失败不影响主流程）
    realtime = None
    if provider == "akshare":
        max_retries = 3
        for attempt in range(max_retries):
            try:
                realtime = fetch_realtime_quote(code, market)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[警告] 实时行情获取失败(尝试 {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
                    time.sleep(2)
                else:
                    print(f"[警告] 实时行情获取失败，已重试 {max_retries} 次: {e}", file=sys.stderr)

    # 获取筹码分布（仅 A股，可选）
    chip = None
    if provider == "akshare" and market == "A股":
        try:
            chip = fetch_chip_distribution(code)
        except Exception as e:
            print(f"[警告] 筹码数据获取失败: {e}", file=sys.stderr)

    return {
        'code': code,
        'name': realtime.get('name', code) if realtime else code,
        'market': market,
        'source': provider,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'klines': klines,
        'realtime': realtime,
        'chip': chip,
    }


def get_project_root() -> str:
    """获取项目根目录（向上4级：scripts -> data-collect -> skills -> project）"""
    current = os.path.abspath(__file__)
    for _ in range(4):
        current = os.path.dirname(current)
    return current


def save_to_file(data: dict, code: str, date_str: str) -> str:
    """保存数据到文件"""
    root = get_project_root()
    output_dir = os.path.join(root, 'output', code, date_str)
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='股票数据收集')
    parser.add_argument('code', help='股票代码（如 600519, AAPL, 00700）')
    parser.add_argument('--days', type=int, default=60, help='获取K线天数（默认60）')
    parser.add_argument(
        '--provider',
        default='akshare',
        choices=['akshare', 'tushare'],
        help='数据源（默认 akshare；仅当用户选择时使用 tushare）'
    )
    parser.add_argument('--date', required=True, help='保存文件的日期标识，格式 YYYY-MM-DD（必填）')
    args = parser.parse_args()

    date_str = args.date

    try:
        result = collect_stock_data(args.code, args.days, args.provider)
        output_path = save_to_file(result, args.code, date_str)

        print(f"[保存] {output_path}", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(1)
