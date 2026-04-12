"""
Phase 1: Parallel fetch — pull data from all sources concurrently.

Uses ThreadPoolExecutor with per-source timeouts.
DCE falls back to akshare if Sina-based fetch fails.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.data_pipeline.state import WorkflowState, PhaseResult, Phase
from src.fetchers import (
    fetch_dce_futures,
    fetch_cbot_soybeans,
    fetch_usdcny,
    fetch_usda_world_psd,
    fetch_usda_china_imports,
    fetch_cot,
)
from .base_phase import BasePhase

logger = logging.getLogger(__name__)

_TIMEOUT = 30


def _fetch_dce() -> dict:
    return {"futures": fetch_dce_futures(["M", "Y", "A"])}


def _fetch_cbot() -> dict:
    result = fetch_cbot_soybeans()
    return {"cbot": result} if result else {"cbot": None}


def _fetch_fx() -> dict:
    rate = fetch_usdcny()
    return {"usdcny": rate}


def _fetch_cot_data() -> dict:
    return {"cot": fetch_cot()}


def _fetch_usda() -> dict:
    world = fetch_usda_world_psd()
    china = fetch_usda_china_imports()
    return {"usda_world": world, "usda_china": china}


_SOURCES: list[tuple[str, Any]] = [
    ("dce", _fetch_dce),
    ("cbot", _fetch_cbot),
    ("fx", _fetch_fx),
    ("cot", _fetch_cot_data),
    ("usda", _fetch_usda),
]


class ParallelFetchPhase(BasePhase):
    name = "PARALLEL_FETCH"

    def execute(self, state: WorkflowState) -> PhaseResult:
        raw: dict[str, Any] = {}
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {pool.submit(fn): name for name, fn in _SOURCES}
            for fut in as_completed(future_map, timeout=_TIMEOUT + 5):
                name = future_map[fut]
                try:
                    result = fut.result(timeout=_TIMEOUT)
                    raw[name] = result
                    logger.info("Fetched %s: %d keys", name, len(result))
                except Exception as e:
                    errors.append(f"{name}: {e}")
                    raw[name] = {"error": str(e)}
                    logger.warning("Fetch %s failed: %s", name, e)

        state.raw_payloads = raw

        # DCE is critical — if missing, escalate
        dce_data = raw.get("dce", {}).get("futures", [])
        if not dce_data:
            errors.append("DCE futures data unavailable — critical failure")
            return PhaseResult(
                next_phase=Phase.ESCALATED,
                errors=errors,
                detail="DCE data missing",
            )

        return PhaseResult(
            next_phase=Phase.CROSS_VALIDATE,
            errors=errors if errors else [],
            detail=f"Fetched {len(raw)} sources, {len(errors)} warnings",
        )
