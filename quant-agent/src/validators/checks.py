"""
Multi-source data validation layer.

No Django dependency — uses akshare directly for reference data.
"""

import logging

logger = logging.getLogger(__name__)

_CRUSH_NORMAL_MIN = -300.0
_CRUSH_NORMAL_MAX = 600.0


def _pct_diff(a: float, b: float) -> float | None:
    if not b:
        return None
    return round(abs(a - b) / abs(b) * 100, 3)


def _result(status: str, primary, reference, deviation_pct, detail: str) -> dict:
    return {
        "status": status,
        "primary": primary,
        "reference": reference,
        "deviation_pct": deviation_pct,
        "detail": detail,
    }


def validate_dce_price(sina_price: float, symbol: str = "M0") -> dict:
    """Cross-check current price against akshare official daily close."""
    try:
        import akshare as ak
        df = ak.futures_main_sina(symbol=symbol)
        if df is None or df.empty:
            return _result("unknown", sina_price, None, None, "参考数据不可用")
        df = df.sort_values("日期").reset_index(drop=True)
        ref_close = float(df.iloc[-1].get("收盘价") or df.iloc[-1].get("动态结算价") or 0)
        if ref_close <= 0:
            return _result("unknown", sina_price, None, None, "参考收盘价为零")
    except Exception as e:
        logger.warning("DCE validator failed %s: %s", symbol, e)
        return _result("unknown", sina_price, None, None, f"参考数据获取失败: {e}")

    dev = _pct_diff(sina_price, ref_close)
    if dev is None:
        return _result("unknown", sina_price, ref_close, None, "偏差计算失败")
    if dev > 10:
        return _result("error", sina_price, ref_close, dev, f"偏差 {dev:.1f}% 超过10% — 可能数据异常")
    if dev > 3:
        return _result("warning", sina_price, ref_close, dev, f"偏差 {dev:.1f}% 超过3% — 请注意核实")
    return _result("ok", sina_price, ref_close, dev, f"偏差 {dev:.1f}% 在正常范围内")


def validate_usdcny(rate: float) -> dict:
    """Cross-check USD/CNY against Bank of China mid rate."""
    try:
        import akshare as ak
        df = ak.currency_boc_sina()
        if df is not None and not df.empty and "央行中间价" in df.columns:
            boc_rate = round(float(df["央行中间价"].iloc[-1]) / 100, 4)
        else:
            return _result("unknown", rate, None, None, "BOC参考汇率不可用")
    except Exception as e:
        logger.warning("BOC rate fetch failed: %s", e)
        return _result("unknown", rate, None, None, f"BOC参考汇率获取失败: {e}")

    dev = _pct_diff(rate, boc_rate)
    if dev and dev > 0.5:
        return _result("warning", rate, boc_rate, dev, f"与中国银行中间价偏差 {dev:.2f}%，超过0.5%阈值")
    return _result("ok", rate, boc_rate, dev, f"与中国银行中间价偏差 {dev:.2f}%，正常")


def validate_crush_margin(margin: float) -> dict:
    """Check crush margin falls within historical range."""
    if margin < _CRUSH_NORMAL_MIN:
        return _result("warning", margin, (_CRUSH_NORMAL_MIN, _CRUSH_NORMAL_MAX), None,
                        f"压榨利润 {margin:.0f} 元/吨 低于历史最低值")
    if margin > _CRUSH_NORMAL_MAX:
        return _result("warning", margin, (_CRUSH_NORMAL_MIN, _CRUSH_NORMAL_MAX), None,
                        f"压榨利润 {margin:.0f} 元/吨 超过历史最高值")
    return _result("ok", margin, (_CRUSH_NORMAL_MIN, _CRUSH_NORMAL_MAX), None,
                    f"压榨利润 {margin:.0f} 元/吨 在历史正常范围内")


def validate_all(dce_prices: list[dict], usdcny: float | None, crush_margin_val: float | None) -> dict:
    """Run all validations and return a summary."""
    results = {}
    for fut in dce_prices:
        results[fut["symbol"]] = validate_dce_price(fut["close"], fut["symbol"])
    if usdcny:
        results["usdcny"] = validate_usdcny(usdcny)
    if crush_margin_val is not None:
        results["crush_margin"] = validate_crush_margin(crush_margin_val)
    return results
