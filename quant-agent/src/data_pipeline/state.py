"""
WorkflowState and PhaseResult — core data structures for the FSM pipeline.

Inspired by pricingblock-exam Q1 Auto-MR checkpoint pattern.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

_CST = timezone(timedelta(hours=8))


class Phase(str, Enum):
    START = "START"
    HEALTH_PROBE = "HEALTH_PROBE"
    PARALLEL_FETCH = "PARALLEL_FETCH"
    CROSS_VALIDATE = "CROSS_VALIDATE"
    NORMALIZE_PUBLISH = "NORMALIZE_PUBLISH"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


@dataclass
class PhaseResult:
    next_phase: Phase
    checkpoint: bool = True
    detail: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class WorkflowState:
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_phase: Phase = Phase.START
    created_at: datetime = field(default_factory=lambda: datetime.now(_CST))
    updated_at: datetime = field(default_factory=lambda: datetime.now(_CST))

    health_probes: dict[str, bool] = field(default_factory=dict)
    raw_payloads: dict[str, Any] = field(default_factory=dict)
    validated_data: dict[str, Any] = field(default_factory=dict)
    market_context: dict[str, Any] = field(default_factory=dict)

    errors: list[str] = field(default_factory=list)
    retry_count: int = 0
    is_terminal: bool = False

    def advance(self, result: PhaseResult) -> None:
        self.current_phase = result.next_phase
        self.updated_at = datetime.now(_CST)
        if result.errors:
            self.errors.extend(result.errors)
        if result.next_phase in (Phase.COMPLETED, Phase.ESCALATED):
            self.is_terminal = True

    def to_checkpoint(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": "data_pipeline",
            "current_phase": self.current_phase.value,
            "state_data": {
                "health_probes": self.health_probes,
                "raw_keys": list(self.raw_payloads.keys()),
                "validated_keys": list(self.validated_data.keys()),
                "errors": self.errors,
                "retry_count": self.retry_count,
            },
            "error_message": "; ".join(self.errors) if self.errors else None,
            "retry_count": self.retry_count,
            "is_terminal": self.is_terminal,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
