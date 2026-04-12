"""DCE futures data via akshare (no Django dependency)."""

import logging
import akshare as ak

logger = logging.getLogger(__name__)

DCE_CONTRACTS = {
    "M0": {"name": "豆粕", "exchange": "DCE", "unit": "元/吨"},
    "Y0": {"name": "豆油", "exchange": "DCE", "unit": "元/吨"},
    "A0": {"name": "黄大豆一号", "exchange": "DCE", "unit": "元/吨"},
}


def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def fetch_dce_futures(contracts: list[str] | None = None) -> list[dict]:
    """Fetch real-time DCE main contract quotes via akshare."""
    wanted = {f"{c}0" if not c.endswith("0") else c for c in (contracts or ["M", "Y", "A"])}
    results = []
    for symbol, meta in DCE_CONTRACTS.items():
        if symbol not in wanted:
            continue
        try:
            df = ak.futures_main_sina(symbol=symbol)
            if df is None or df.empty:
                continue
            df = df.sort_values("日期").reset_index(drop=True)
            row = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else row
            close = _safe_float(row.get("收盘价") or row.get("动态结算价"))
            prev_close = _safe_float(prev.get("收盘价") or prev.get("动态结算价"))
            change = round(close - prev_close, 2) if prev_close else 0.0
            change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
            results.append({
                "symbol": symbol,
                "name": meta["name"],
                "exchange": meta["exchange"],
                "unit": meta["unit"],
                "close": close,
                "open": _safe_float(row.get("开盘价")),
                "high": _safe_float(row.get("最高价")),
                "low": _safe_float(row.get("最低价")),
                "volume": _safe_int(row.get("成交量")),
                "open_interest": _safe_int(row.get("持仓量")),
                "date": str(row.get("日期", "")),
                "change": change,
                "change_pct": change_pct,
            })
        except Exception as e:
            logger.warning("DCE %s fetch failed: %s", symbol, e)
    return results


def fetch_dce_history(symbol: str, days: int = 180) -> list[dict]:
    """Fetch historical daily OHLCV for a DCE main contract."""
    try:
        df = ak.futures_main_sina(symbol=symbol)
        if df is None or df.empty:
            return []
        df = df.sort_values("日期").tail(days).reset_index(drop=True)
        return [
            {
                "date": str(r["日期"]),
                "open": _safe_float(r.get("开盘价")),
                "high": _safe_float(r.get("最高价")),
                "low": _safe_float(r.get("最低价")),
                "close": _safe_float(r.get("收盘价") or r.get("动态结算价")),
                "volume": _safe_int(r.get("成交量")),
            }
            for _, r in df.iterrows()
        ]
    except Exception as e:
        logger.warning("DCE history %s failed: %s", symbol, e)
        return []
