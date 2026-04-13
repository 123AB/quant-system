"""
Signal agent HTTP service interface.

Exposes SynthesizeSignal and GetLatestSignal as JSON-over-HTTP endpoints,
matching the proto definitions in agent/signal_service.proto.

Lightweight alternative to full gRPC — callable by Java biz-service or Go gateway.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

import psycopg
import redis as redis_sync

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant_dev_2026@localhost:5432/quant")
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_SERVICE_PORT = int(os.getenv("SIGNAL_SERVICE_PORT", "50052"))


def _synthesize_signal() -> dict:
    """Trigger one round of signal synthesis."""
    from src.signal_agent.graph import build_signal_graph
    from datetime import date

    t0 = time.monotonic()
    graph = build_signal_graph()
    config = {"configurable": {"thread_id": f"signal-api-{date.today()}"}}
    result = graph.invoke({}, config=config)
    elapsed = int((time.monotonic() - t0) * 1000)

    return {
        "request_id": result.get("snapshot_id", ""),
        "signal": {
            "direction": result.get("signal_direction", "neutral"),
            "confidence": result.get("confidence", 0),
            "signal_type": "llm_synthesis",
            "reasoning_chain": result.get("reasoning_chain", []),
            "escalated": result.get("escalated", False),
            "escalate_reason": result.get("escalate_reason"),
            "timestamp": datetime.now(_CST).isoformat(),
        },
        "elapsed_ms": elapsed,
    }


def _get_latest_signal() -> dict:
    """Read latest signal from Redis or PostgreSQL."""
    try:
        r = redis_sync.from_url(_REDIS_URL, decode_responses=True)
        cached = r.hgetall("soy:signal:latest")
        if cached:
            return {
                "direction": cached.get("direction", "neutral"),
                "confidence": float(cached.get("confidence", 0)),
                "signal_type": cached.get("signal_type", "unknown"),
                "escalated": cached.get("escalated", "false") == "true",
                "timestamp": cached.get("updated_at", ""),
                "source": "redis_cache",
            }
    except Exception as e:
        logger.warning("Redis read failed: %s", e)

    try:
        with psycopg.connect(_DATABASE_URL) as conn:
            row = conn.execute(
                """SELECT direction, confidence, signal_type, escalated, time
                   FROM signal_history
                   ORDER BY time DESC LIMIT 1"""
            ).fetchone()
            if row:
                return {
                    "direction": row[0],
                    "confidence": float(row[1]) if row[1] else 0,
                    "signal_type": row[2],
                    "escalated": row[3],
                    "timestamp": row[4].isoformat() if row[4] else "",
                    "source": "postgresql",
                }
    except Exception as e:
        logger.warning("PG read failed: %s", e)

    return {"error": "no signal available"}


class _SignalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {"status": "ok", "service": "signal-agent"})
        elif self.path == "/signal/latest":
            result = _get_latest_signal()
            self._json_response(200, result)
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/signal/synthesize":
            try:
                result = _synthesize_signal()
                self._json_response(200, result)
            except Exception as e:
                logger.error("Synthesis failed: %s", e, exc_info=True)
                self._json_response(500, {"error": str(e)})
        else:
            self._json_response(404, {"error": "not found"})

    def _json_response(self, code: int, data: dict):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_signal_service(port: int = _SERVICE_PORT) -> Thread:
    """Start the signal HTTP service in a background thread."""
    server = HTTPServer(("0.0.0.0", port), _SignalHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Signal service listening on :%d", port)
    return thread
