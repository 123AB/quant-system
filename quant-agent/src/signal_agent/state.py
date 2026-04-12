"""SignalState — TypedDict for the LangGraph signal synthesis workflow."""

from typing import TypedDict, Literal, Any


class SignalState(TypedDict, total=False):
    # Input
    market_context: dict[str, Any]
    snapshot_id: str
    started_at: str

    # Context engineering
    compressed_context: str
    token_estimate: int

    # LLM reasoning
    tool_calls: list[dict[str, Any]]
    reasoning_chain: list[str]

    # Output
    signal: dict[str, Any] | None
    confidence: float
    signal_direction: Literal["bullish", "bearish", "neutral"]

    # Escalation
    escalated: bool
    escalate_reason: str | None

    # Metadata
    data_quality: Literal["fresh", "stale", "degraded"]
    stale_source_count: int
    elapsed_ms: int
    persist_ok: bool
