"""
Phase 2: Cross-validation — verify data consistency across sources.

Reuses validator logic from src.validators for DCE, FX, crush margin checks.
"""

from __future__ import annotations

import logging
from typing import Any

from src.data_pipeline.state import WorkflowState, PhaseResult, Phase
from src.crusher import landed_cost, crush_margin
from .base_phase import BasePhase

logger = logging.getLogger(__name__)

_CRUSH_RANGE = (-300.0, 600.0)


def _pct_diff(a: float, b: float) -> float | None:
    if not b:
        return None
    return round(abs(a - b) / abs(b) * 100, 3)


class CrossValidatePhase(BasePhase):
    name = "CROSS_VALIDATE"

    def execute(self, state: WorkflowState) -> PhaseResult:
        raw = state.raw_payloads
        warnings: list[str] = []
        validated: dict[str, Any] = {}

        # 1. DCE futures
        dce_futures = raw.get("dce", {}).get("futures", [])
        validated["dce_futures"] = dce_futures
        for fut in dce_futures:
            close = fut.get("close", 0)
            if close <= 0:
                warnings.append(f"DCE {fut.get('symbol')}: close={close} invalid")

        # 2. CBOT
        cbot = raw.get("cbot", {}).get("cbot")
        validated["cbot"] = cbot
        if cbot and cbot.get("close", 0) <= 0:
            warnings.append(f"CBOT close={cbot.get('close')} invalid")

        # 3. USD/CNY sanity check
        usdcny = raw.get("fx", {}).get("usdcny")
        validated["usdcny"] = usdcny
        if usdcny and not (6.0 < usdcny < 8.5):
            warnings.append(f"USD/CNY={usdcny} outside sane range [6.0, 8.5]")

        # 4. Crush margin range check
        prices = {f["symbol"]: f["close"] for f in dce_futures if f.get("close", 0) > 0}
        meal = prices.get("M0", 0)
        oil = prices.get("Y0", 0)
        cbot_cents = cbot["close"] if cbot else 0

        crush_data = None
        if all([meal, oil, cbot_cents, usdcny]):
            lc = landed_cost(cbot_cents, 45.0, usdcny)
            cm = crush_margin(meal, oil, lc["total_bean_cost_cny"])
            margin = cm["crush_margin_cny"]
            crush_data = {**lc, **cm, "meal_price": meal, "oil_price": oil}
            validated["crush"] = crush_data

            if margin < _CRUSH_RANGE[0] or margin > _CRUSH_RANGE[1]:
                warnings.append(
                    f"Crush margin {margin:.0f} outside range [{_CRUSH_RANGE[0]}, {_CRUSH_RANGE[1]}]"
                )
        else:
            validated["crush"] = None
            warnings.append("Insufficient data for crush margin calculation")

        # 5. COT + USDA + Inventory (pass through, low priority)
        validated["cot"] = raw.get("cot", {}).get("cot", {})
        validated["usda_world"] = raw.get("usda", {}).get("usda_world", {})
        validated["usda_china"] = raw.get("usda", {}).get("usda_china", [])
        validated["inventory"] = raw.get("inventory", {}).get("inventory", {})

        state.validated_data = validated

        error_count = sum(1 for w in warnings if "invalid" in w.lower())
        if error_count >= 2:
            return PhaseResult(
                next_phase=Phase.ESCALATED,
                errors=warnings,
                detail=f"{error_count} critical validation failures",
            )

        return PhaseResult(
            next_phase=Phase.NORMALIZE_PUBLISH,
            errors=warnings if warnings else [],
            detail=f"Validated with {len(warnings)} warnings",
        )
