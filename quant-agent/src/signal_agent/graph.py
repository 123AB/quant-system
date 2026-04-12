"""
LangGraph signal synthesis workflow.

StateGraph: gather_data → compress → llm_reasoning → (emit|escalate) → persist
"""

from langgraph.graph import StateGraph, START, END

from src.signal_agent.state import SignalState
from src.signal_agent.nodes import (
    gather_market_data,
    compress_context,
    llm_reasoning_with_tools,
    route_by_confidence,
    emit_signal,
    escalate_to_human,
    persist_signal,
)


def build_signal_graph() -> StateGraph:
    """Build and compile the signal synthesis StateGraph."""
    graph = StateGraph(SignalState)

    graph.add_node("gather_data", gather_market_data)
    graph.add_node("compress_context", compress_context)
    graph.add_node("llm_reasoning", llm_reasoning_with_tools)
    graph.add_node("emit_signal", emit_signal)
    graph.add_node("escalate", escalate_to_human)
    graph.add_node("persist_signal", persist_signal)

    graph.add_edge(START, "gather_data")
    graph.add_edge("gather_data", "compress_context")
    graph.add_edge("compress_context", "llm_reasoning")

    graph.add_conditional_edges(
        "llm_reasoning",
        route_by_confidence,
        {"confident": "emit_signal", "uncertain": "escalate"},
    )

    graph.add_edge("emit_signal", "persist_signal")
    graph.add_edge("escalate", "persist_signal")
    graph.add_edge("persist_signal", END)

    return graph.compile()
