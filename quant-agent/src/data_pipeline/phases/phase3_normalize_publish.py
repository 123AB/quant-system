"""
Phase 3: Normalize and publish — write to PostgreSQL + Redis + Redis Stream.

Builds MarketContext, persists to TimescaleDB hypertable and Redis cache,
then publishes an event to Redis Stream for downstream consumers.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

import psycopg
import redis

from src.data_pipeline.state import WorkflowState, PhaseResult, Phase
from .base_phase import BasePhase

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant_dev_2026@localhost:5432/quant")


def _build_market_context(validated: dict) -> dict:
    """Assemble normalized MarketContext from validated data."""
    now = datetime.now(_CST)
    snapshot_id = str(uuid.uuid4())

    dce = {}
    for fut in validated.get("dce_futures", []):
        dce[fut["symbol"]] = {
            "close": fut["close"],
            "open": fut["open"],
            "high": fut["high"],
            "low": fut["low"],
            "volume": fut["volume"],
            "change_pct": fut["change_pct"],
            "name": fut["name"],
            "unit": fut["unit"],
        }

    return {
        "snapshot_id": snapshot_id,
        "timestamp": now.isoformat(),
        "dce_quotes": dce,
        "cbot": validated.get("cbot"),
        "usdcny": validated.get("usdcny"),
        "crush": validated.get("crush"),
        "cot": validated.get("cot"),
        "usda_world": validated.get("usda_world"),
        "usda_china": validated.get("usda_china"),
        "inventory": validated.get("inventory", {}),
    }


def _write_pg(ctx: dict) -> None:
    """Insert market quotes into TimescaleDB hypertable."""
    now = datetime.now(_CST)
    rows = []

    for symbol, quote in ctx.get("dce_quotes", {}).items():
        rows.append((
            now, "sina", symbol,
            quote.get("open"), quote.get("high"), quote.get("low"), quote.get("close"),
            quote.get("volume"), None, quote.get("change_pct"), "live",
        ))

    cbot = ctx.get("cbot")
    if cbot:
        rows.append((
            now, "akshare", cbot.get("symbol", "S"),
            cbot.get("open"), cbot.get("high"), cbot.get("low"), cbot.get("close"),
            None, None, cbot.get("change_pct"), "delayed",
        ))

    crush = ctx.get("crush")
    if crush:
        with psycopg.connect(_DATABASE_URL) as conn:
            conn.execute(
                """INSERT INTO crush_margin_history
                   (time, meal_price, oil_price, cbot_cents, usdcny, freight_usd,
                    landed_cost_cny, total_revenue_cny, crush_margin_cny, signal)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    now, crush.get("meal_price"), crush.get("oil_price"),
                    crush.get("cbot_usd_per_ton"), ctx.get("usdcny"),
                    crush.get("freight_usd"), crush.get("landed_cost_cny"),
                    crush.get("total_revenue_cny"), crush.get("crush_margin_cny"),
                    crush.get("signal"),
                ),
            )

    if rows:
        with psycopg.connect(_DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO market_quotes
                       (time, source, symbol, open, high, low, close, volume, amount, change_pct, data_quality)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    rows,
                )
            conn.commit()

    # Save snapshot
    with psycopg.connect(_DATABASE_URL) as conn:
        conn.execute(
            "INSERT INTO market_snapshot (id, time, context, data_quality) VALUES (%s, %s, %s, %s)",
            (ctx["snapshot_id"], now, json.dumps(ctx, default=str), "live"),
        )
        conn.commit()

    logger.info("PG: wrote %d market_quotes + 1 crush_margin + 1 snapshot", len(rows))


def _write_redis(ctx: dict) -> None:
    """Cache latest context in Redis + publish event to Stream."""
    r = redis.from_url(_REDIS_URL, decode_responses=True)

    # Cache individual quotes
    for symbol, quote in ctx.get("dce_quotes", {}).items():
        key = f"soy:dce:{symbol}"
        r.hset(key, mapping={k: str(v) for k, v in quote.items()})
        r.expire(key, 120)

    cbot = ctx.get("cbot")
    if cbot:
        r.hset("soy:cbot:latest", mapping={k: str(v) for k, v in cbot.items()})
        r.expire("soy:cbot:latest", 1800)

    if ctx.get("usdcny"):
        r.set("soy:fx:usdcny", str(ctx["usdcny"]), ex=120)

    crush = ctx.get("crush")
    if crush:
        r.hset("soy:crush:latest", mapping={k: str(v) for k, v in crush.items()})
        r.expire("soy:crush:latest", 120)

    cot = ctx.get("cot")
    if cot:
        r.hset("soy:cot:latest", mapping={k: str(v) for k, v in cot.items()})
        r.expire("soy:cot:latest", 86400)

    usda_world = ctx.get("usda_world")
    if usda_world:
        r.set("soy:usda:world", json.dumps(usda_world, default=str), ex=21600)

    usda_china = ctx.get("usda_china")
    if usda_china:
        r.set("soy:usda:china", json.dumps(usda_china, default=str), ex=21600)

    inventory = ctx.get("inventory")
    if inventory:
        r.set("soy:inventory:latest", json.dumps(inventory, default=str), ex=7200)

    # Factor signal (computed from live basis + panel)
    try:
        from src.factor_signal.engine import compute_signal
        signal = compute_signal()
        if signal and "error" not in signal:
            r.set("soy:factor_signal:latest", json.dumps(signal, default=str), ex=1800)
            logger.info("Redis: cached factor signal (score=%s)", signal.get("composite_score"))
    except Exception as e:
        logger.warning("Factor signal computation failed: %s", e)

    # Full context JSON
    r.set("market:context:latest", json.dumps(ctx, default=str), ex=120)

    # Redis Stream event
    r.xadd("quant:market_events", {
        "type": "market_context_updated",
        "snapshot_id": ctx["snapshot_id"],
        "timestamp": ctx["timestamp"],
    }, maxlen=1000)

    logger.info("Redis: cached context + published stream event")


class NormalizePublishPhase(BasePhase):
    name = "NORMALIZE_PUBLISH"

    def execute(self, state: WorkflowState) -> PhaseResult:
        ctx = _build_market_context(state.validated_data)
        state.market_context = ctx

        errors: list[str] = []

        try:
            _write_pg(ctx)
        except Exception as e:
            errors.append(f"PG write failed: {e}")
            logger.error("PG write failed: %s", e)

        try:
            _write_redis(ctx)
        except Exception as e:
            errors.append(f"Redis write failed: {e}")
            logger.error("Redis write failed: %s", e)

        if len(errors) == 2:
            return PhaseResult(
                next_phase=Phase.ESCALATED,
                errors=errors,
                detail="Both PG and Redis writes failed",
            )

        return PhaseResult(
            next_phase=Phase.COMPLETED,
            errors=errors,
            detail=f"Published snapshot {ctx['snapshot_id'][:8]}",
        )
