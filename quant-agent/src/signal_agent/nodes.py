"""
LangGraph node implementations for signal synthesis.

Nodes: gather_market_data, compress_context, llm_reasoning_with_tools,
       emit_signal, escalate_to_human, persist_signal
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

import psycopg
import redis as redis_sync

from src.signal_agent.state import SignalState

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant_dev_2026@localhost:5432/quant")


# ─── Node 1: Gather Market Data ─────────────────────────────────────────────

def gather_market_data(state: SignalState) -> dict:
    """Read latest MarketContext from Redis (written by data-pipeline)."""
    r = redis_sync.from_url(_REDIS_URL, decode_responses=True)

    context = {}
    # DCE quotes
    for sym in ["M0", "Y0", "A0"]:
        data = r.hgetall(f"soy:dce:{sym}")
        if data:
            context[f"dce_{sym.lower()}"] = data

    # CBOT
    cbot = r.hgetall("soy:cbot:latest")
    if cbot:
        context["cbot"] = cbot

    # FX
    usdcny = r.get("soy:fx:usdcny")
    if usdcny:
        context["usdcny"] = usdcny

    # Crush
    crush = r.hgetall("soy:crush:latest")
    if crush:
        context["crush"] = crush

    # COT
    cot = r.hgetall("soy:cot:latest")
    if cot:
        context["cot"] = cot

    # Rule-based signal (from factor_signal)
    rule = r.hgetall("soy:signal:rule")
    if rule:
        context["rule_signal"] = rule

    stale_count = sum(1 for v in context.values() if not v)
    snapshot_id = str(uuid.uuid4())

    return {
        "market_context": context,
        "snapshot_id": snapshot_id,
        "started_at": datetime.now(_CST).isoformat(),
        "stale_source_count": stale_count,
        "data_quality": "degraded" if stale_count >= 3 else ("stale" if stale_count >= 1 else "fresh"),
    }


# ─── Node 2: Compress Context ───────────────────────────────────────────────

def compress_context(state: SignalState) -> dict:
    """
    Compress MarketContext into <2000 token text for LLM.

    Token budget allocation (pricingblock-exam Q2 pattern):
    - P0 (must-have): current prices, crush margin, signal direction ~500 tokens
    - P1 (compressed): factor scores, COT net, USDA S/U ratio ~600 tokens
    - P2 (conditional): only abnormal indicators ~400 tokens
    - P3 (dropped): normal-range details → replaced by "XX正常"
    """
    ctx = state.get("market_context", {})
    lines = []

    # P0: Core data
    lines.append(f"## 当前行情 ({state.get('started_at', 'N/A')})")

    dce_m0 = ctx.get("dce_m0", {})
    dce_y0 = ctx.get("dce_y0", {})
    cbot = ctx.get("cbot", {})
    lines.append(f"豆粕M0: {dce_m0.get('close', 'N/A')} 元/吨 (涨跌 {dce_m0.get('change_pct', 'N/A')}%)")
    lines.append(f"豆油Y0: {dce_y0.get('close', 'N/A')} 元/吨")
    lines.append(f"CBOT大豆: {cbot.get('close', 'N/A')} 美分/蒲")
    lines.append(f"USD/CNY: {ctx.get('usdcny', 'N/A')}")

    # P0: Crush margin
    crush = ctx.get("crush", {})
    margin = _safe_float(crush.get("crush_margin_cny"))
    if margin is not None:
        lines.append(f"\n## 压榨利润")
        lines.append(f"当前: {margin:.0f} 元/吨 ({crush.get('signal', 'N/A')})")
        if margin < -50 or margin > 400:
            lines.append(f"⚠ 利润处于极端水平")
    else:
        lines.append("\n## 压榨利润: 数据不可用")

    # P1: Rule engine signal
    rule = ctx.get("rule_signal", {})
    if rule:
        lines.append(f"\n## 规则引擎参考")
        lines.append(f"方向: {rule.get('direction', 'N/A')}, 得分: {rule.get('score', 'N/A')}")

    # P2: COT — only if abnormal
    cot = ctx.get("cot", {})
    if cot:
        net_change = _safe_float(cot.get("soy_net_change"))
        if net_change is not None and abs(net_change) > 20000:
            lines.append(f"\n## COT 持仓异常")
            lines.append(f"5日净变化: {net_change:.0f} 手（超过 2 万手阈值）")
        else:
            lines.append(f"\nCOT持仓: 正常范围")

    # P1: Data quality
    dq = state.get("data_quality", "unknown")
    if dq != "fresh":
        lines.append(f"\n⚠ 数据质量: {dq} ({state.get('stale_source_count', 0)} 个数据源过期)")

    compressed = "\n".join(lines)
    token_est = len(compressed) // 3  # rough CJK token estimate

    return {
        "compressed_context": compressed,
        "token_estimate": token_est,
    }


# ─── Node 3: LLM Reasoning ──────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位专注于大豆产业链的量化研究员。

## 分析框架（wn170411 分析师方法论）
- 价格触及支撑位 + 成交量突增 → 底部确认，分批建多头
- 自底部累涨 1000-1200 元/吨 → 分批减仓，不追高
- 美豆大跌但国内不跟 → 国内内生强势，维持多头
- 6-9月 09合约季节性偏多

## 输出要求
你必须输出一个 JSON 对象（不要加 markdown 代码块）：
{
  "direction": "做多" | "观望" | "做空",
  "confidence": 0.0-1.0,
  "reasoning_chain": ["步骤1", "步骤2", ...],
  "key_factors": ["因子1", "因子2"],
  "risk_warnings": ["风险1"],
  "escalate": false,
  "escalate_reason": null
}"""


def llm_reasoning_with_tools(state: SignalState) -> dict:
    """LLM reasoning with function calling (ReAct loop, max 5 rounds)."""
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
    from src.signal_agent.tools import SIGNAL_TOOLS
    from src.signal_agent.llm_provider import get_llm

    llm = get_llm().bind_tools(SIGNAL_TOOLS)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=state.get("compressed_context", "数据不可用")),
    ]

    tool_calls_log = []
    reasoning = []

    tool_map = {t.name: t for t in SIGNAL_TOOLS}

    for round_num in range(5):
        response = llm.invoke(messages)

        if response.tool_calls:
            messages.append(response)
            for tc in response.tool_calls:
                tool_calls_log.append({"tool": tc["name"], "args": tc["args"], "round": round_num})
                reasoning.append(f"调用工具 {tc['name']}: {tc['args']}")
                try:
                    tool_fn = tool_map[tc["name"]]
                    result = tool_fn.invoke(tc["args"])
                    messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                except Exception as e:
                    messages.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc["id"]))
        else:
            signal = _parse_signal_json(response.content)
            reasoning.append(f"最终判断: {signal.get('direction', 'N/A')}")
            return {
                "signal": signal,
                "confidence": signal.get("confidence", 0),
                "signal_direction": _map_direction(signal.get("direction", "观望")),
                "tool_calls": tool_calls_log,
                "reasoning_chain": reasoning,
                "escalated": signal.get("escalate", False),
                "escalate_reason": signal.get("escalate_reason"),
            }

    return {
        "escalated": True,
        "escalate_reason": "LLM推理轮次超限 (>5 rounds)",
        "reasoning_chain": reasoning,
        "tool_calls": tool_calls_log,
    }


# ─── Node 4: Route by confidence ────────────────────────────────────────────

def route_by_confidence(state: SignalState) -> str:
    if state.get("escalated"):
        return "uncertain"
    confidence = state.get("confidence", 0)
    if confidence >= 0.6:
        return "confident"
    return "uncertain"


# ─── Node 5: Emit Signal ────────────────────────────────────────────────────

def emit_signal(state: SignalState) -> dict:
    """Publish the signal to Redis for downstream consumers."""
    signal = state.get("signal", {})
    if not signal:
        return {}

    try:
        r = redis_sync.from_url(_REDIS_URL, decode_responses=True)
        r.hset("soy:signal:latest", mapping={
            "direction": signal.get("direction", ""),
            "confidence": str(signal.get("confidence", 0)),
            "signal_type": "llm_synthesis",
            "updated_at": datetime.now(_CST).isoformat(),
            "escalated": "false",
        })
        r.expire("soy:signal:latest", 1800)

        r.xadd("quant:market_events", {
            "type": "signal_updated",
            "direction": signal.get("direction", ""),
            "confidence": str(signal.get("confidence", 0)),
        }, maxlen=1000)
    except Exception as e:
        logger.error("Failed to publish signal to Redis: %s", e)

    return {}


# ─── Node 6: Escalate ───────────────────────────────────────────────────────

def escalate_to_human(state: SignalState) -> dict:
    """
    Pause workflow using LangGraph interrupt() for human review.
    If interrupt() is not available (e.g., no checkpointer), falls back to logging.
    """
    reason = state.get("escalate_reason", "置信度不足")
    logger.warning("Signal ESCALATED: %s", reason)

    try:
        r = redis_sync.from_url(_REDIS_URL, decode_responses=True)
        r.xadd("quant:alerts", {
            "type": "signal_escalated",
            "reason": reason,
            "proposed_direction": state.get("signal", {}).get("direction", "N/A"),
            "confidence": str(state.get("confidence", 0)),
            "timestamp": datetime.now(_CST).isoformat(),
        }, maxlen=1000)
    except Exception as e:
        logger.error("Failed to publish escalation alert: %s", e)

    # Use LangGraph interrupt() when checkpointer is configured
    try:
        from langgraph.types import interrupt
        human_response = interrupt({
            "type": "signal_review",
            "reason": reason,
            "proposed_signal": state.get("signal"),
            "reasoning_chain": state.get("reasoning_chain"),
            "message": f"信号需要人工审核: {reason}",
        })
        if human_response and human_response.get("approved"):
            return {"escalated": False}
        return {
            "escalated": True,
            "escalate_reason": f"人工否决: {human_response.get('reason', '')}",
        }
    except Exception:
        # No checkpointer or interrupt not supported — proceed with escalated=True
        return {"escalated": True}


# ─── Node 7: Persist Signal (with A/B comparison) ───────────────────────────

def persist_signal(state: SignalState) -> dict:
    """
    Write both LLM signal and rule-based signal to PostgreSQL signal_history.
    This enables A/B comparison between the two approaches.
    """
    signal = state.get("signal", {})
    now = datetime.now(_CST)
    persist_ok = False

    # 1. Persist LLM signal
    try:
        with psycopg.connect(_DATABASE_URL) as conn:
            conn.execute(
                """INSERT INTO signal_history
                   (time, signal_type, direction, confidence, composite_score,
                    factors, reasoning_chain, escalated, escalate_reason, market_snapshot_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    now,
                    "llm_synthesis" if signal else "escalated",
                    state.get("signal_direction", "neutral"),
                    state.get("confidence", 0),
                    signal.get("composite_score", 0) if signal else 0,
                    json.dumps(signal.get("key_factors", []), ensure_ascii=False),
                    json.dumps(state.get("reasoning_chain", []), ensure_ascii=False),
                    state.get("escalated", False),
                    state.get("escalate_reason"),
                    state.get("snapshot_id"),
                ),
            )
            conn.commit()
        persist_ok = True
    except Exception as e:
        logger.error("Failed to persist LLM signal: %s", e)

    # 2. A/B: also run and persist rule-based signal for comparison
    _persist_rule_based_signal(state, now)

    started = state.get("started_at", "")
    elapsed = 0
    if started:
        try:
            start_dt = datetime.fromisoformat(started)
            elapsed = int((now - start_dt).total_seconds() * 1000)
        except Exception:
            pass

    return {"persist_ok": persist_ok, "elapsed_ms": elapsed}


def _persist_rule_based_signal(state: SignalState, now: datetime) -> None:
    """Run the rule-based factor signal engine and persist alongside LLM signal."""
    try:
        from src.factor_signal.engine import compute_factor_signal
        ctx = state.get("market_context", {})

        dce_m0 = ctx.get("dce_m0", {})
        crush = ctx.get("crush", {})
        cot = ctx.get("cot", {})

        meal_close = _safe_float(dce_m0.get("close"))
        crush_margin = _safe_float(crush.get("crush_margin_cny"))

        if meal_close is None or meal_close <= 0:
            return

        rule_result = compute_factor_signal(meal_close)

        direction_map = {"强烈做多": "bullish", "做多": "bullish",
                         "观望偏多": "bullish", "观望": "neutral", "偏空": "bearish"}
        direction = direction_map.get(rule_result.get("composite_signal", ""), "neutral")

        with psycopg.connect(_DATABASE_URL) as conn:
            conn.execute(
                """INSERT INTO signal_history
                   (time, signal_type, direction, confidence, composite_score,
                    factors, reasoning_chain, escalated, escalate_reason, market_snapshot_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    now,
                    "rule_based",
                    direction,
                    1.0,
                    rule_result.get("composite_score", 0),
                    json.dumps(rule_result.get("factors", []), ensure_ascii=False),
                    json.dumps(["rule_based_engine"], ensure_ascii=False),
                    False,
                    None,
                    state.get("snapshot_id"),
                ),
            )
            conn.commit()
        logger.info("A/B: rule-based signal persisted (score=%s, direction=%s)",
                     rule_result.get("composite_score"), direction)
    except Exception as e:
        logger.warning("A/B rule-based signal failed (non-fatal): %s", e)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _parse_signal_json(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {
            "direction": "观望",
            "confidence": 0.3,
            "reasoning_chain": ["JSON解析失败，降级为观望"],
            "key_factors": [],
            "risk_warnings": ["LLM输出格式异常"],
            "escalate": True,
            "escalate_reason": "LLM输出无法解析为JSON",
        }


def _map_direction(cn_direction: str) -> str:
    mapping = {"做多": "bullish", "做空": "bearish", "观望": "neutral"}
    return mapping.get(cn_direction, "neutral")
