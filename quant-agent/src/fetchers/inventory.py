"""DCE warehouse receipt inventory via akshare."""

import logging
import akshare as ak

logger = logging.getLogger(__name__)

_PRODUCTS = {
    "豆粕": {"key": "M", "name": "豆粕"},
    "豆油": {"key": "Y", "name": "豆油"},
    "豆一": {"key": "A", "name": "黄大豆一号"},
}


def fetch_dce_inventory() -> dict:
    """Fetch DCE warehouse receipt inventory for soybean products."""
    result = {}
    for cn_name, meta in _PRODUCTS.items():
        try:
            df = ak.futures_inventory_em(symbol=cn_name)
            if df is None or df.empty:
                continue
            df = df.sort_values("日期").reset_index(drop=True)
            records = []
            for _, row in df.tail(30).iterrows():
                inv = int(float(row.get("仓单数量", 0)))
                chg = int(float(row.get("增减", 0)))
                records.append({
                    "date": str(row.get("日期", ""))[:10],
                    "inventory": inv,
                    "change": chg,
                })
            latest = records[-1] if records else None
            result[meta["key"]] = {
                "name": meta["name"],
                "records": records,
                "latest": latest,
            }
        except Exception as e:
            logger.warning("DCE inventory %s failed: %s", cn_name, e)
            result[meta["key"]] = {"name": meta["name"], "records": [], "latest": None, "error": str(e)}
    return result
