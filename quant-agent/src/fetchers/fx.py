"""USD/CNY exchange rate via akshare."""

import logging
import akshare as ak

logger = logging.getLogger(__name__)


def fetch_usdcny() -> float | None:
    """Fetch USD/CNY rate from Bank of China via akshare."""
    try:
        df = ak.currency_boc_sina()
        if df is not None and not df.empty and "央行中间价" in df.columns:
            val = df["央行中间价"].iloc[-1]
            rate = round(float(val) / 100, 4)
            if 6.0 < rate < 8.5:
                return rate
    except Exception as e:
        logger.warning("USD/CNY fetch failed: %s", e)
    logger.warning("USD/CNY fallback to 7.24")
    return 7.24
