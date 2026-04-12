"""
Phase 0: Health probe — check data source reachability before fetching.

Light-weight HEAD or small GET requests to verify Sina, akshare, USDA are up.
"""

from __future__ import annotations

import logging
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.data_pipeline.state import WorkflowState, PhaseResult, Phase
from .base_phase import BasePhase

logger = logging.getLogger(__name__)

_PROBES = {
    "sina": "https://hq.sinajs.cn/list=nf_M0",
    "usda": "https://apps.fas.usda.gov/PSDOnlineDataServices/api/CommodityData/GetCommodityGroups",
}

_TIMEOUT = 10


def _probe_url(name: str, url: str) -> tuple[str, bool, str]:
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "quant-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return name, resp.status < 400, ""
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
            futures = {pool.submit(_probe_url, name, url): name for name, url in _PROBES.items()}
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
