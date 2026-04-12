"""
Quantitative factor signal engine (no Django dependency).

Reads factor_panel.csv and supplements with live basis data from akshare.
"""

import logging
import math
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

KEY_PRICE_LEVELS = [3000, 3200, 3300, 3400, 3600, 3800, 4000, 4300]

ANALYST_RULES = [
    "价格触及支撑位 + 成交量突增 → 底部确认，分批建多头仓位",
    "自底部累涨 1000–1200 元/吨 → 分批减仓离场，不追高",
    "美豆大跌但国内不跟 → 国内内生强势，维持多头；6–9月 09合约季节性偏多",
]

_THRESHOLDS = {
    "support_distance_strong": -0.02,
    "support_distance_mild": 0.00,
    "volume_bottom_confirm": 1.50,
    "cbot_div_strong": 0.002,
    "cbot_div_lag": 0.00,
    "seasonality_bull": 0.50,
    "seasonality_bear": -0.20,
    "basis_chg_bull": -20.0,
    "crush_rate_bear": -0.50,
}


def _safe(val, default=None):
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _score_and_describe(row: dict) -> tuple[int, list[dict]]:
    score = 0
    factors = []

    def add(name, label, value, pts, signal, desc):
        nonlocal score
        score += pts
        factors.append({
            "name": name, "label": label,
            "value": round(value, 4) if value is not None else None,
            "signal": signal, "description": desc, "points": pts,
        })

    sd = _safe(row.get("support_distance"))
    if sd is not None:
        if sd < _THRESHOLDS["support_distance_strong"]:
            add("support_distance", "支撑距离", sd, +2, "bullish", f"价格已跌破支撑位 {abs(sd)*100:.1f}%")
        elif sd < _THRESHOLDS["support_distance_mild"]:
            add("support_distance", "支撑距离", sd, +1, "bullish", f"价格接近支撑位（距离 {abs(sd)*100:.1f}%）")
        else:
            add("support_distance", "支撑距离", sd, 0, "neutral", f"价格高于支撑位 {sd*100:.1f}%")
    else:
        add("support_distance", "支撑距离", None, 0, "neutral", "数据不可用")

    vb = _safe(row.get("volume_bottom"))
    near_support = sd is not None and sd < 0.03
    if vb is not None and near_support and vb > _THRESHOLDS["volume_bottom_confirm"]:
        add("volume_bottom", "量能底部", vb, +3, "bullish", f"成交量是5日均量的 {vb:.2f}× → 底部确认")
    elif vb is not None:
        add("volume_bottom", "量能底部", vb, 0, "neutral", f"成交量是5日均量的 {vb:.2f}×")
    else:
        add("volume_bottom", "量能底部", None, 0, "neutral", "数据不可用")

    cd = _safe(row.get("cbot_divergence"))
    if cd is not None:
        if cd > _THRESHOLDS["cbot_div_strong"]:
            add("cbot_divergence", "内外盘背离", cd, +1, "bullish", f"国内日涨幅比美豆高 {cd*100:.2f}%")
        else:
            add("cbot_divergence", "内外盘背离", cd, 0, "neutral", f"内外盘背离 {cd*100:.2f}%")
    else:
        add("cbot_divergence", "内外盘背离", None, 0, "neutral", "数据不可用")

    cd1 = _safe(row.get("cbot_divergence_lag1"))
    if cd1 is not None:
        if cd1 > _THRESHOLDS["cbot_div_lag"]:
            add("cbot_divergence_lag1", "滞后背离确认", cd1, +1, "bullish", f"前一日国内也跑赢美豆（{cd1*100:.2f}%）")
        else:
            add("cbot_divergence_lag1", "滞后背离确认", cd1, 0, "neutral", f"前一日未见背离（{cd1*100:.2f}%）")
    else:
        add("cbot_divergence_lag1", "滞后背离确认", None, 0, "neutral", "数据不可用")

    sea = _safe(row.get("seasonality"))
    if sea is not None:
        if sea >= _THRESHOLDS["seasonality_bull"]:
            add("seasonality", "季节性", sea, +1, "bullish", "6–9月历史强势窗口")
        elif sea < _THRESHOLDS["seasonality_bear"]:
            add("seasonality", "季节性", sea, -1, "bearish", "季节性偏空")
        else:
            add("seasonality", "季节性", sea, 0, "neutral", "季节性中性")
    else:
        add("seasonality", "季节性", None, 0, "neutral", "数据不可用")

    bc5 = _safe(row.get("basis_chg5"))
    if bc5 is not None:
        if bc5 < _THRESHOLDS["basis_chg_bull"]:
            add("basis_chg5", "基差变化(5日)", bc5, +1, "bullish", f"5日基差收窄 {bc5:.0f} 元/吨")
        elif bc5 > 20.0:
            add("basis_chg5", "基差变化(5日)", bc5, -1, "bearish", f"5日基差走扩 {bc5:.0f} 元/吨")
        else:
            add("basis_chg5", "基差变化(5日)", bc5, 0, "neutral", f"5日基差变化 {bc5:.0f} 元/吨")
    else:
        add("basis_chg5", "基差变化(5日)", None, 0, "neutral", "基差数据获取中…")

    crc = _safe(row.get("crush_rate_chg"))
    if crc is not None:
        if crc < _THRESHOLDS["crush_rate_bear"]:
            add("crush_rate_chg", "开机率变化", crc, +1, "bullish", f"开机率5日变化 {crc:.2f}%，供给收缩")
        else:
            add("crush_rate_chg", "开机率变化", crc, 0, "neutral", f"开机率5日变化 {crc:.2f}%")
    else:
        add("crush_rate_chg", "开机率变化", None, 0, "neutral", "开机率数据暂不可用")

    basis_val = _safe(row.get("basis"))
    add("basis", "现货基差", basis_val, 0, "neutral",
        f"现货−期货基差 {basis_val:.0f} 元/吨" if basis_val is not None else "现货基差数据获取中…")

    return score, factors


def _signal_label(score: int) -> str:
    if score >= 5: return "强烈做多"
    if score >= 3: return "做多"
    if score >= 1: return "观望偏多"
    if score == 0: return "观望"
    return "偏空"


def _signal_level(score: int) -> str:
    if score >= 3: return "bullish"
    if score >= 1: return "neutral_bullish"
    if score == 0: return "neutral"
    return "bearish"


def compute_signal(panel_path: str | Path | None = None) -> dict:
    """Load latest row from factor_panel.csv and return composite signal."""
    if panel_path is None:
        panel_path = Path(__file__).resolve().parents[4] / "text-factor-miner" / "output" / "factor_panel.csv"
    panel_path = Path(panel_path)

    try:
        df = pd.read_csv(panel_path)
        if df.empty:
            raise ValueError("factor_panel.csv is empty")
        df = df.sort_values("date").reset_index(drop=True)
        row = df.iloc[-1].to_dict()
        latest_date = str(row.get("date", ""))
    except Exception as e:
        logger.warning("factor_signal: cannot load panel from %s: %s", panel_path, e)
        return {"error": f"因子面板加载失败: {e}", "panel_path": str(panel_path)}

    try:
        from src.fetchers.basis import fetch_basis_m
        basis_records = fetch_basis_m(trading_days=15)
        if basis_records and len(basis_records) >= 2:
            latest = basis_records[-1]
            old = basis_records[-min(6, len(basis_records))]
            row["basis"] = latest["basis"]
            row["basis_chg5"] = latest["basis"] - old["basis"]
            latest_date = latest["date"]
        elif basis_records:
            row["basis"] = basis_records[-1]["basis"]
    except Exception as e:
        logger.warning("factor_signal: basis supplement failed: %s", e)

    score, factors = _score_and_describe(row)

    return {
        "date": latest_date,
        "composite_score": score,
        "composite_signal": _signal_label(score),
        "signal_level": _signal_level(score),
        "factors": factors,
        "key_price_levels": KEY_PRICE_LEVELS,
        "analyst_rules": ANALYST_RULES,
        "total_factors": len(factors),
    }
