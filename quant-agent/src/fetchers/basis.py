"""Spot-futures basis for 豆粕 (M) via akshare."""

import logging
from datetime import date, timedelta

import akshare as ak

logger = logging.getLogger(__name__)


def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def fetch_basis_m(trading_days: int = 15) -> list[dict]:
    """Fetch recent spot-futures basis for 豆粕 (M)."""
    end = date.today()
    start = end - timedelta(days=trading_days * 2)
    try:
        df = ak.futures_spot_price_daily(
            start_day=start.strftime("%Y%m%d"),
            end_day=end.strftime("%Y%m%d"),
            vars_list=["M"],
        )
        if df is None or df.empty:
            return []
        df = df.sort_values("date").reset_index(drop=True)
        records = []
        for _, row in df.iterrows():
            try:
                basis_val = float(row.get("near_basis"))
            except (TypeError, ValueError):
                continue
            records.append({
                "date": str(row["date"])[:10],
                "spot": _safe_float(row.get("spot_price")),
                "futures": _safe_float(row.get("near_price")),
                "basis": basis_val,
            })
        return records[-trading_days:]
    except Exception as e:
        logger.warning("fetch_basis_m failed: %s", e)
        return []
