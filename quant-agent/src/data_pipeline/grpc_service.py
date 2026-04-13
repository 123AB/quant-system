"""
gRPC-like status service for the data pipeline.

Exposes pipeline health and last run status via a simple JSON-over-HTTP interface
(lightweight alternative to full gRPC, callable by Java biz-service).

Run alongside the scheduler or as a standalone endpoint.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

import psycopg

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant_dev_2026@localhost:5432/quant")
_STATUS_PORT = int(os.getenv("PIPELINE_STATUS_PORT", "50051"))


def _get_latest_workflow() -> dict | None:
    try:
        with psycopg.connect(_DATABASE_URL) as conn:
            row = conn.execute(
                """SELECT id, workflow_type, current_phase, state_data,
                          error_message, retry_count, is_terminal, updated_at
                   FROM workflow_state
                   ORDER BY updated_at DESC
                   LIMIT 1"""
            ).fetchone()
            if row:
                return {
                    "workflow_id": str(row[0]),
                    "workflow_type": row[1],
                    "current_phase": row[2],
                    "state_data": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                    "error_message": row[4],
                    "retry_count": row[5],
                    "is_terminal": row[6],
                    "updated_at": row[7].isoformat() if row[7] else None,
                }
    except Exception as e:
        logger.error("Failed to query workflow_state: %s", e)
    return None


class _StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {"status": "ok", "service": "data-pipeline"})
        elif self.path == "/status":
            wf = _get_latest_workflow()
            self._json_response(200, {
                "status": "ok",
                "latest_workflow": wf,
                "timestamp": datetime.now(_CST).isoformat(),
            })
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


def start_status_server(port: int = _STATUS_PORT) -> Thread:
    """Start the status HTTP server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), _StatusHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Pipeline status server listening on :%d", port)
    return thread
