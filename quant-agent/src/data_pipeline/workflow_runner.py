"""
WorkflowRunner — FSM orchestrator that drives phases in sequence.

Each phase produces a PhaseResult indicating the next state.
State is checkpointed to PostgreSQL after each phase transition.
Inspired by pricingblock-exam Q1 Auto-MR phase runner.
"""

from __future__ import annotations

import json
import logging
import os
import time

import psycopg

from src.data_pipeline.state import WorkflowState, Phase
from src.data_pipeline.phases import (
    HealthProbePhase,
    ParallelFetchPhase,
    CrossValidatePhase,
    NormalizePublishPhase,
)

logger = logging.getLogger(__name__)

_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant_dev_2026@localhost:5432/quant")

_PHASE_MAP = {
    Phase.HEALTH_PROBE: HealthProbePhase(),
    Phase.PARALLEL_FETCH: ParallelFetchPhase(),
    Phase.CROSS_VALIDATE: CrossValidatePhase(),
    Phase.NORMALIZE_PUBLISH: NormalizePublishPhase(),
}

_TRANSITION = {
    Phase.START: Phase.HEALTH_PROBE,
}


def _checkpoint(state: WorkflowState) -> None:
    """Persist workflow state to PostgreSQL."""
    try:
        data = state.to_checkpoint()
        with psycopg.connect(_DATABASE_URL) as conn:
            conn.execute(
                """INSERT INTO workflow_state
                   (id, workflow_type, current_phase, state_data, error_message, retry_count, is_terminal, updated_at)
                   VALUES (%(workflow_id)s, %(workflow_type)s, %(current_phase)s,
                           %(state_data)s::jsonb, %(error_message)s, %(retry_count)s, %(is_terminal)s, now())
                   ON CONFLICT (id) DO UPDATE SET
                       current_phase = EXCLUDED.current_phase,
                       state_data = EXCLUDED.state_data,
                       error_message = EXCLUDED.error_message,
                       retry_count = EXCLUDED.retry_count,
                       is_terminal = EXCLUDED.is_terminal,
                       updated_at = now()""",
                {
                    **data,
                    "state_data": json.dumps(data["state_data"]),
                },
            )
            conn.commit()
    except Exception as e:
        logger.warning("Checkpoint write failed (non-fatal): %s", e)


def run_pipeline() -> WorkflowState:
    """Execute the full data pipeline FSM from START to COMPLETED or ESCALATED."""
    state = WorkflowState()
    t0 = time.monotonic()

    logger.info("Pipeline %s starting", state.workflow_id[:8])

    # START → HEALTH_PROBE
    state.current_phase = Phase.HEALTH_PROBE
    _checkpoint(state)

    while not state.is_terminal:
        phase_impl = _PHASE_MAP.get(state.current_phase)
        if phase_impl is None:
            logger.error("No implementation for phase %s", state.current_phase)
            break

        result = phase_impl.run(state)
        state.advance(result)

        if result.checkpoint:
            _checkpoint(state)

    elapsed = (time.monotonic() - t0) * 1000
    logger.info(
        "Pipeline %s finished → %s (%.0fms, %d errors)",
        state.workflow_id[:8], state.current_phase.value, elapsed, len(state.errors),
    )

    return state
