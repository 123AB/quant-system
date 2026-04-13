"""CFTC Commitments of Traders via akshare."""

import logging
import akshare as ak

logger = logging.getLogger(__name__)


def _safe_int(v, default=0) -> int:
    try:
        return int(float(v)) if v is not None and str(v) != "nan" else default
    except (TypeError, ValueError):
        return default


def fetch_cot() -> dict:
    """Fetch CFTC COT for CBOT soybeans / soybean meal."""
    try:
        df = ak.macro_usa_cftc_c_holding()
        if df is None or df.empty:
            return {}
        df = df.sort_values("日期").reset_index(drop=True)
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row
        soy_net = _safe_int(row.get("大豆-净仓位", 0))
        prev_soy_net = _safe_int(prev.get("大豆-净仓位", 0))
        soy_long = _safe_int(row.get("大豆-多头仓位", 0))
        soy_short = _safe_int(row.get("大豆-空头仓位", 0))
        meal_long = _safe_int(row.get("豆粕-多头仓位", 0))
        meal_short = _safe_int(row.get("豆粕-空头仓位", 0))
        meal_net = _safe_int(row.get("豆粕-净仓位", 0))
        return {
            "date": str(row.get("日期", "")),
            # Proto-aligned names (CotPositioning message)
            "non_commercial_long": soy_long,
            "non_commercial_short": soy_short,
            "non_commercial_net": soy_net,
            "net_change_5d": soy_net - prev_soy_net,
            "commercial_long": meal_long,
            "commercial_short": meal_short,
            "commercial_net": meal_net,
            # Legacy names (backward compatibility with fund-tracker frontend)
            "soy_long": soy_long,
            "soy_short": soy_short,
            "soy_net": soy_net,
            "soy_net_change": soy_net - prev_soy_net,
            "meal_long": meal_long,
            "meal_short": meal_short,
            "meal_net": meal_net,
        }
    except Exception as e:
        logger.warning("CFTC COT fetch failed: %s", e)
        return {}
