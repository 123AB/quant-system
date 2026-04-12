"""CBOT soybean futures via akshare."""

import logging
import akshare as ak

logger = logging.getLogger(__name__)


def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def fetch_cbot_soybeans() -> dict | None:
    """Fetch CBOT soybean continuous contract (US cents/bushel)."""
    try:
        df = ak.futures_foreign_hist(symbol="S")
        if df is None or df.empty:
            return None
        df = df.sort_values("date").reset_index(drop=True)
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row
        close = _safe_float(row.get("close"))
        prev_close = _safe_float(prev.get("close"))
        change = round(close - prev_close, 4)
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
        return {
            "symbol": "S",
            "name": "美豆(CBOT)",
            "exchange": "CBOT",
            "unit": "美分/蒲式耳",
            "close": close,
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "date": str(row.get("date", "")),
            "change": change,
            "change_pct": change_pct,
        }
    except Exception as e:
        logger.warning("CBOT fetch failed: %s", e)
        return None
