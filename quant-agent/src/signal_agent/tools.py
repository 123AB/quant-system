"""
Function calling tools for the signal-agent LLM.

These are the same underlying functions as the MCP tools,
registered as LangChain tools for use in the LangGraph workflow.
"""

from langchain_core.tools import tool

from src.fetchers import fetch_usda_world_psd, fetch_usda_china_imports
from src.fetchers.dce import fetch_dce_history


@tool
def get_historical_percentile(metric: str, lookback_days: int = 252) -> dict:
    """查询某个指标在历史区间中的分位数位置，判断当前值是否处于极端水平。

    Args:
        metric: 指标名称，可选 crush_margin, basis, cot_net_long
        lookback_days: 回看天数，默认252（一年交易日）
    """
    history = fetch_dce_history("M0", days=lookback_days)
    if not history:
        return {"error": "历史数据不可用", "metric": metric}

    closes = [h["close"] for h in history if h["close"] > 0]
    if len(closes) < 20:
        return {"error": "历史数据不足", "metric": metric, "count": len(closes)}

    closes.sort()
    current = closes[-1]
    rank = sum(1 for c in closes if c <= current)
    percentile = round(rank / len(closes), 3)

    return {
        "metric": metric,
        "current_value": current,
        "percentile": percentile,
        "lookback_days": len(closes),
        "min": closes[0],
        "max": closes[-1],
        "p25": closes[len(closes) // 4],
        "median": closes[len(closes) // 2],
        "p75": closes[3 * len(closes) // 4],
        "interpretation": f"当前值处于近{len(closes)}日 {percentile*100:.0f}% 分位",
    }


@tool
def get_usda_supply_demand(region: str = "world") -> dict:
    """获取USDA全球或中国大豆供需平衡表。

    Args:
        region: world=全球平衡表, china=中国进口数据
    """
    if region == "china":
        data = fetch_usda_china_imports()
        return {"china_imports": data, "unit": "千吨"}
    else:
        data = fetch_usda_world_psd()
        return {"world_balance": data, "unit": "千吨(MMT)"}


@tool
def get_seasonal_pattern(month: int, contract: str = "M") -> dict:
    """查询历史同期的豆粕价格涨跌规律。

    Args:
        month: 月份 1-12
        contract: 合约代码，默认M（豆粕）
    """
    seasonal_map = {
        1: {"direction": "neutral", "note": "春节前备货需求，但南美丰收预期压制"},
        2: {"direction": "bearish", "note": "南美大豆集中上市，供应压力大"},
        3: {"direction": "neutral", "note": "南美收获进入尾声，关注美国种植意向"},
        4: {"direction": "neutral", "note": "美国播种开始，天气市前的平静期"},
        5: {"direction": "bullish", "note": "美国播种进展 + 天气不确定性开始升温"},
        6: {"direction": "bullish", "note": "天气市高峰，关注美国中西部降水"},
        7: {"direction": "bullish", "note": "美豆关键生长期，天气溢价往往最高"},
        8: {"direction": "bullish", "note": "结荚-灌浆期，任何干旱都可能大幅推高价格"},
        9: {"direction": "neutral_bullish", "note": "收获前最后炒作窗口，09合约历史从未持续下跌"},
        10: {"direction": "bearish", "note": "美国收获压力，大量大豆上市"},
        11: {"direction": "neutral", "note": "收获压力减退，南美播种开始"},
        12: {"direction": "neutral", "note": "市场关注南美天气和年度报告"},
    }
    info = seasonal_map.get(month, {"direction": "unknown", "note": "无数据"})
    return {
        "month": month,
        "contract": contract,
        "seasonal_direction": info["direction"],
        "note": info["note"],
    }


SIGNAL_TOOLS = [get_historical_percentile, get_usda_supply_demand, get_seasonal_pattern]
