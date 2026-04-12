"""
BasePhase — abstract template method for pipeline phases.

Inspired by pricingblock-exam Q1 Auto-MR PhaseRunner pattern.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from src.data_pipeline.state import WorkflowState, PhaseResult, Phase

logger = logging.getLogger(__name__)


class BasePhase(ABC):
    """Template Method pattern: setup → execute → teardown with timing and error handling."""

    name: str = "base"

    def run(self, state: WorkflowState) -> PhaseResult:
        logger.info("[%s] Phase %s starting", state.workflow_id[:8], self.name)
        t0 = time.monotonic()
        try:
            result = self.execute(state)
            elapsed = (time.monotonic() - t0) * 1000
            logger.info(
                "[%s] Phase %s → %s (%.0fms)",
                state.workflow_id[:8], self.name, result.next_phase.value, elapsed,
            )
            return result
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error(
                "[%s] Phase %s FAILED (%.0fms): %s",
                state.workflow_id[:8], self.name, elapsed, e,
            )
            return PhaseResult(
                next_phase=Phase.ESCALATED,
                errors=[f"{self.name}: {e}"],
                detail=str(e),
            )

    @abstractmethod
    def execute(self, state: WorkflowState) -> PhaseResult:
        ...
