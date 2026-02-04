#!/usr/bin/env python3
"""
AI 决策脚本

用法:
    python decision.py 600519 --date 2025-01-01
    python decision.py 600519 --date 2025-01-01 --news "新闻内容"

输入: output/<code>/<date>/analysis.json
输出: output/<code>/<date>/decision.json
"""

import json
import os
import sys
import argparse
from datetime import datetime


def get_score_level(score: int) -> tuple:
    """根据分数返回操作建议"""
    if score >= 80:
        return ("强烈看多", "买入", "buy", "高")
    elif score >= 60:
        return ("看多", "轻仓买入", "buy", "中")
    elif score >= 40:
        return ("震荡", "观望", "hold", "中")
    else:
        return ("看空", "卖出", "sell", "低")


def generate_checklist(analysis: dict, chip: dict = None) -> list:
    """生成检查清单"""
    checklist = []

    # 1. 多头排列检查
    trend = analysis.get('trend', {})
    if trend.get('status_code') in ['STRONG_BULL', 'BULL']:
        checklist.append(f"[YES] 多头排列：{trend.get('ma_alignment', 'MA5>MA10>MA20')} 满足")
    elif trend.get('status_code') == 'WEAK_BULL':
        checklist.append(f"[WARN] 弱势多头：{trend.get('ma_alignment', '')}，趋势待确认")
    else:
        checklist.append(f"[NO] 趋势不佳：{trend.get('status', '非多头排列')}，不宜做多")

    # 2. 乖离率检查
    bias = analysis.get('bias', {})
    bias_val = bias.get('ma5', 0)
    if abs(bias_val) < 2:
        checklist.append(f"[YES] 乖离率<5%：当前{bias_val:.1f}%，最佳买点区间")
    elif abs(bias_val) < 5:
        checklist.append(f"[WARN] 乖离率{bias_val:.1f}%：接近警戒线，可小仓介入")
    else:
        checklist.append(f"[NO] 乖离率{bias_val:.1f}%>5%：严禁追高")

    # 3. 量能配合检查
    volume = analysis.get('volume', {})
    vol_status = volume.get('status', '')
    if vol_status == 'SHRINK_VOLUME_DOWN':
        checklist.append(f"[YES] 量能配合：{volume.get('status_desc', '缩量回调')}，洗盘特征")
    elif vol_status in ['HEAVY_VOLUME_UP', 'NORMAL']:
        checklist.append(f"[YES] 量能配合：{volume.get('status_desc', '量能正常')}")
    elif vol_status == 'HEAVY_VOLUME_DOWN':
        checklist.append(f"[NO] 量能警告：{volume.get('status_desc', '放量下跌')}，注意风险")
    else:
        checklist.append(f"[WARN] 量能一般：{volume.get('status_desc', '')}")

    # 4. 舆情检查（默认）
    checklist.append("[YES] 无重大利空：舆情正常")

    # 5. 筹码结构检查
    if chip:
        profit_ratio = chip.get('profit_ratio', 0)
        if profit_ratio and profit_ratio > 0:
            if profit_ratio < 0.7:
                checklist.append(f"[YES] 筹码结构：获利盘{profit_ratio*100:.0f}%，筹码稳定")
            elif profit_ratio < 0.9:
                checklist.append(f"[WARN] 筹码结构：获利盘{profit_ratio*100:.0f}%，注意回吐风险")
            else:
                checklist.append(f"[NO] 筹码结构：获利盘{profit_ratio*100:.0f}%>90%，获利盘过重")
    else:
        checklist.append("[WARN] 筹码结构：数据缺失，无法判断")

    # 6. 买点位置检查
    support = analysis.get('support_resistance', {})
    if support.get('support_ma5'):
        checklist.append("[YES] 买点位置：价格在MA5支撑位，理想买点")
    elif support.get('support_ma10'):
        checklist.append("[YES] 买点位置：价格在MA10支撑位，次优买点")
    elif bias_val < 2:
        checklist.append("[WARN] 买点位置：价格略高于MA5，可小仓试探")
    else:
        checklist.append("[NO] 买点位置：当前价高于理想买点，等待回踩")

    return checklist


def calculate_price_levels(analysis: dict) -> dict:
    """计算精确狙击点位"""
    price = analysis.get('price', {})
    current = price.get('current', 0)
    ma5 = price.get('ma5', 0)
    ma10 = price.get('ma10', 0)
    ma20 = price.get('ma20', 0)

    support = analysis.get('support_resistance', {})
    resistance = support.get('resistance_levels', [])

    ideal_buy = round(ma5, 2) if ma5 else round(current * 0.98, 2)
    secondary_buy = round(ma10, 2) if ma10 else round(current * 0.95, 2)
    stop_loss = round(ma20 * 0.98, 2) if ma20 else round(current * 0.95, 2)

    if resistance:
        take_profit = round(resistance[0], 2)
    else:
        take_profit = round(current * 1.10, 2)

    risk = ideal_buy - stop_loss
    reward = take_profit - ideal_buy
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0

    return {
        'current_price': current,
        'ideal_buy': ideal_buy,
        'secondary_buy': secondary_buy,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'risk_reward_ratio': rr_ratio
    }


def generate_core_conclusion(analysis: dict, price_levels: dict) -> dict:
    """生成核心结论"""
    signal = analysis.get('signal', {})
    trend = analysis.get('trend', {})
    bias = analysis.get('bias', {})

    action = signal.get('action', '观望')
    score = signal.get('score', 50)
    bias_val = bias.get('ma5', 0)

    if trend.get('status_code') in ['BEAR', 'STRONG_BEAR']:
        one_sentence = f"空头趋势，不参与，等待趋势反转"
        signal_type = "SELL"
        time_sensitivity = "立即行动"
    elif bias_val > 5:
        one_sentence = f"多头趋势但乖离率{bias_val:.1f}%过高，严禁追高，等待回踩MA5"
        signal_type = "HOLD"
        time_sensitivity = "本周内"
    elif action == "强烈买入":
        one_sentence = f"多头趋势+位置理想+量价配合，可积极介入"
        signal_type = "BUY"
        time_sensitivity = "今日内"
    elif action == "买入":
        one_sentence = f"趋势良好，部分条件满足，建议轻仓试探"
        signal_type = "BUY"
        time_sensitivity = "今日内"
    elif action in ["持有", "观望"]:
        one_sentence = f"趋势尚可但条件不充分，等待更好时机"
        signal_type = "HOLD"
        time_sensitivity = "本周内"
    else:
        one_sentence = f"条件较差，建议减仓或离场"
        signal_type = "SELL"
        time_sensitivity = "今日内"

    ideal_buy = price_levels.get('ideal_buy', 0)
    stop_loss = price_levels.get('stop_loss', 0)
    take_profit = price_levels.get('take_profit', 0)

    if action in ["强烈买入", "买入"]:
        no_position = f"空仓者：可在{ideal_buy}元附近建仓，首仓30-50%"
        has_position = f"持仓者：继续持有，止损{stop_loss}元，目标{take_profit}元"
    elif action in ["持有", "观望"]:
        no_position = f"空仓者：等待回踩{ideal_buy}元(MA5附近)再介入"
        has_position = f"持仓者：继续持有，设好止损{stop_loss}元"
    else:
        no_position = f"空仓者：保持观望，不宜入场"
        has_position = f"持仓者：考虑减仓或止损离场"

    return {
        'one_sentence': one_sentence,
        'signal_type': signal_type,
        'time_sensitivity': time_sensitivity,
        'position_advice': {
            'no_position': no_position,
            'has_position': has_position
        }
    }


def parse_news_intelligence(news_context: str = None) -> dict:
    """解析舆情情报"""
    if not news_context:
        return {
            'latest_news': '未获取到相关新闻',
            'risk_alerts': [],
            'positive_catalysts': [],
            'sentiment_summary': '舆情数据缺失，请关注公告'
        }

    risk_alerts = []
    positive_catalysts = []

    risk_keywords = ['减持', '处罚', '立案', '调查', '亏损', '下滑', '解禁', '质押']
    for keyword in risk_keywords:
        if keyword in news_context:
            risk_alerts.append(f"检测到「{keyword}」相关信息")

    positive_keywords = ['增长', '超预期', '中标', '合同', '利好', '突破', '新高', '分红']
    for keyword in positive_keywords:
        if keyword in news_context:
            positive_catalysts.append(f"检测到「{keyword}」相关信息")

    latest_news = news_context[:100] + "..." if len(news_context) > 100 else news_context

    if len(risk_alerts) > len(positive_catalysts):
        sentiment = "舆情偏负面，注意风险"
    elif len(positive_catalysts) > len(risk_alerts):
        sentiment = "舆情偏正面，有利好支撑"
    else:
        sentiment = "舆情中性，无重大利空利好"

    return {
        'latest_news': latest_news,
        'risk_alerts': risk_alerts[:3],
        'positive_catalysts': positive_catalysts[:3],
        'sentiment_summary': sentiment
    }


def ai_decision(analysis: dict, news_context: str = None) -> dict:
    """主决策函数"""
    code = analysis.get('code', 'Unknown')
    name = analysis.get('name', code)

    # chip 数据由 technical-analysis 透传
    chip = analysis.get('chip')

    price_levels = calculate_price_levels(analysis)
    core_conclusion = generate_core_conclusion(analysis, price_levels)
    checklist = generate_checklist(analysis, chip)
    intelligence = parse_news_intelligence(news_context)

    # 更新舆情检查项
    if intelligence['risk_alerts']:
        for i, item in enumerate(checklist):
            if '舆情' in item or '利空' in item:
                checklist[i] = f"[WARN] 舆情风险：{intelligence['risk_alerts'][0]}"
                break

    signal = analysis.get('signal', {})
    trend = analysis.get('trend', {})
    price = analysis.get('price', {})
    bias = analysis.get('bias', {})

    return {
        'code': code,
        'name': name,
        'decision_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

        'core_conclusion': core_conclusion,
        'price_levels': price_levels,
        'checklist': checklist,
        'intelligence': intelligence,

        'summary': {
            'action': signal.get('action', '观望'),
            'confidence': '高' if signal.get('score', 0) >= 75 else '中' if signal.get('score', 0) >= 50 else '低',
            'score': signal.get('score', 50)
        },

        'trend_status': trend.get('status', ''),
        'current_price': price.get('current', 0),
        'bias_ma5': bias.get('ma5', 0)
    }


def get_project_root() -> str:
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AI 决策分析')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('--date', required=True, help='日期，格式 YYYY-MM-DD')
    parser.add_argument('--news', type=str, help='新闻舆情内容')
    args = parser.parse_args()

    root = get_project_root()

    # 读取分析文件
    input_path = os.path.join(root, 'output', args.code, args.date, 'analysis.json')
    if not os.path.exists(input_path):
        print(f"[错误] 分析文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    if analysis.get('ok') is False or analysis.get('error'):
        print(
            f"[错误] technical-analysis 输出无效: {analysis.get('error', 'unknown error')}. "
            f"请先修复上游分析并重跑 technical-analysis（code={args.code}, date={args.date}）。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 执行决策
    result = ai_decision(analysis, news_context=args.news)

    # 保存结果
    output_dir = os.path.join(root, 'output', args.code, args.date)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'decision.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[读取] {input_path}", file=sys.stderr)
    print(f"[保存] {output_path}", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2))
