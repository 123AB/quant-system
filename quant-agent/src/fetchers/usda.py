"""USDA FAS PSD Online API fetchers."""

import logging

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://apps.fas.usda.gov/PSDOnlineDataServices/api"


def _usda_get(path: str) -> list:
    url = f"{_API_BASE}/{path}"
    resp = httpx.get(url, headers={"Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_usda_world_psd() -> dict:
    """World soybean supply/demand balance from USDA FAS PSD Online."""
    try:
        data = _usda_get("CommodityData/CommoditySupplyAndUse?commodityCode=2222000&countryCode=00&marketYear=0")
        rows = sorted(data, key=lambda x: x.get("marketYear", 0), reverse=True)[:3]
        result = {}
        for r in rows:
            yr = str(r.get("marketYear"))
            tu = r.get("totalUse") or 1
            es = r.get("endingStocks") or 0
            result[yr] = {
                "marketing_year": r.get("marketYear"),
                "production": r.get("production"),
                "imports": r.get("myImports"),
                "total_supply": r.get("totalSupply"),
                "crush": r.get("crush"),
                "total_use": r.get("totalUse"),
                "ending_stocks": es,
                "sc_ratio": round(es / tu * 100, 1) if tu else None,
            }
        return result
    except Exception as e:
        logger.warning("USDA world PSD failed: %s", e)
        return {}


def fetch_usda_china_imports() -> list[dict]:
    """China soybean import history from USDA FAS PSD Online."""
    try:
        data = _usda_get("CommodityData/CommoditySupplyAndUse?commodityCode=2222000&countryCode=CH&marketYear=0")
        rows = sorted(data, key=lambda x: x.get("marketYear", 0), reverse=True)[:6]
        return [
            {
                "marketing_year": r.get("marketYear"),
                "imports": r.get("myImports"),
                "crush": r.get("crush"),
                "ending_stocks": r.get("endingStocks"),
                "total_use": r.get("totalUse"),
                "sc_ratio": (
                    round((r["endingStocks"] or 0) / (r["totalUse"] or 1) * 100, 1)
                    if r.get("totalUse")
                    else None
                ),
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("USDA China imports failed: %s", e)
        return []
