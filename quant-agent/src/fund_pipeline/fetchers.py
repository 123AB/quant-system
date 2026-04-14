"""
LOF fund data fetchers — standalone (no Django dependency).

Uses Sina Finance for real-time prices/indices and fundgz for NAV.
"""

import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "Referer": "http://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}
_TIMEOUT = 8.0
_SINA_BASE = "http://hq.sinajs.cn/list="


def _sina_batch(codes: list[str]) -> dict[str, list[str]]:
    if not codes:
        return {}
    url = _SINA_BASE + ",".join(codes)
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        text = resp.content.decode("gbk", errors="replace")
    except Exception as exc:
        logger.warning("Sina batch failed for %d codes: %s", len(codes), exc)
        return {}

    result: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = re.match(r'var hq_str_(\S+?)="([^"]*)"', line)
        if m:
            result[m.group(1)] = m.group(2).split(",")
    return result


def fetch_lof_prices(fund_rows: list[dict]) -> dict[str, dict]:
    """
    Batch-fetch LOF market prices from Sina.
    fund_rows: list of dicts with keys 'code', 'exchange'.
    """
    code_map = {}
    sina_codes = []
    for fc in fund_rows:
        sina_code = f"{fc['exchange']}{fc['code']}"
        sina_codes.append(sina_code)
        code_map[sina_code] = fc["code"]

    raw = _sina_batch(sina_codes)
    prices: dict[str, dict] = {}
    for sina_code, fields in raw.items():
        fund_code = code_map.get(sina_code)
        if not fund_code or len(fields) < 10:
            continue
        try:
            prev_close = float(fields[2]) if fields[2] else 0.0
            price = float(fields[3]) if fields[3] else 0.0
            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            volume_wan = round(float(fields[9]) / 10_000, 2) if fields[9] else 0.0
            prices[fund_code] = {
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "volume_wan": volume_wan,
                "open": float(fields[1]) if fields[1] else 0.0,
                "high": float(fields[4]) if fields[4] else 0.0,
                "low": float(fields[5]) if fields[5] else 0.0,
            }
        except (ValueError, IndexError) as exc:
            logger.debug("Price parse error for %s: %s", fund_code, exc)
    return prices


def fetch_index_changes(index_sina_codes: list[str]) -> dict[str, dict]:
    raw = _sina_batch(index_sina_codes)
    indices: dict[str, dict] = {}
    for code in index_sina_codes:
        fields = raw.get(code, [])
        if len(fields) < 4:
            continue
        try:
            indices[code] = {
                "name": fields[0],
                "price": float(fields[1]) if fields[1] else 0.0,
                "change_pct": float(fields[3]) if fields[3] else 0.0,
            }
        except (ValueError, IndexError) as exc:
            logger.debug("Index parse error for %s: %s", code, exc)
    return indices


def _fetch_single_nav(code: str) -> dict | None:
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        m = re.search(r"\{(.+)\}", resp.text)
        if not m:
            return None
        data = json.loads("{" + m.group(1) + "}")
        nav = data.get("dwjz", "")
        if nav:
            return {
                "nav": nav,
                "nav_date": data.get("jzrq", ""),
                "gsz": data.get("gsz", ""),
            }
    except Exception as exc:
        logger.debug("NAV fetch failed for %s: %s", code, exc)
    return None


def fetch_navs(codes: list[str], max_workers: int = 12) -> dict[str, dict]:
    result: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_single_nav, c): c for c in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                nav_data = future.result()
                if nav_data:
                    result[code] = nav_data
            except Exception:
                pass
    return result
