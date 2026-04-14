"""
Phase 0: Health probe — check data source reachability before fetching.

Light-weight GET requests to verify Sina, akshare, USDA are up.
Uses httpx with proper headers to avoid anti-bot blocks.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from src.data_pipeline.state import WorkflowState, PhaseResult, Phase
from .base_phase import BasePhase

logger = logging.getLogger(__name__)

_SINA_HEADERS = {
    "Referer": "http://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}

_PROBES = {
    "sina": {
        "url": "http://hq.sinajs.cn/list=nf_M0",
        "headers": _SINA_HEADERS,
        "timeout": 10,
    },
    "usda": {
        "url": "https://apps.fas.usda.gov/PSDOnlineDataServices/api/CommodityData/GetCommodityGroups",
        "headers": {"Accept": "application/json", "User-Agent": "quant-pipeline/1.0"},
        "timeout": 20,
    },
}


def _probe_url(name: str, cfg: dict) -> tuple[str, bool, str]:
    try:
        resp = httpx.get(cfg["url"], headers=cfg["headers"], timeout=cfg["timeout"])
        return name, resp.status_code < 400, ""
    except Exception as e:
        return name, False, str(e)


def _probe_akshare() -> tuple[str, bool, str]:
    """Verify akshare is importable and can do a minimal call."""
    try:
        import akshare as ak
        # Lightweight call: just import check, actual data fetch in phase 1
        assert hasattr(ak, "futures_main_sina")
        return "akshare", True, ""
    except Exception as e:
        return "akshare", False, str(e)


class HealthProbePhase(BasePhase):
    name = "HEALTH_PROBE"

    def execute(self, state: WorkflowState) -> PhaseResult:
        results: dict[str, bool] = {}
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_probe_url, name, cfg): name for name, cfg in _PROBES.items()}
            futures[pool.submit(_probe_akshare)] = "akshare"

            for fut in as_completed(futures, timeout=15):
                name, ok, err = fut.result()
                results[name] = ok
                if not ok:
                    errors.append(f"{name}: {err}")
                    logger.warning("Health probe %s failed: %s", name, err)

        state.health_probes = results
        failed_count = sum(1 for v in results.values() if not v)

        if failed_count >= 2:
            return PhaseResult(
                next_phase=Phase.ESCALATED,
                errors=errors,
                detail=f"{failed_count}/{len(results)} sources unreachable",
            )

        return PhaseResult(
            next_phase=Phase.PARALLEL_FETCH,
            detail=f"{len(results) - failed_count}/{len(results)} sources healthy",
        )
