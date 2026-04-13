"""
Signal agent entry point with APScheduler.

Runs LangGraph signal synthesis every 30 minutes during trading hours,
and every 2 hours during off-hours.

Run: python -m src.signal_agent.main
"""

import logging
import os
import signal
import sys
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("signal_agent")


def _run_signal_synthesis():
    """Execute one round of LangGraph signal synthesis."""
    from src.signal_agent.graph import build_signal_graph

    try:
        graph = build_signal_graph()
        config = {"configurable": {"thread_id": f"signal-{date.today()}"}}
        result = graph.invoke({}, config=config)

        direction = result.get("signal_direction", "N/A")
        confidence = result.get("confidence", 0)
        escalated = result.get("escalated", False)
        elapsed = result.get("elapsed_ms", 0)

        if escalated:
            logger.warning(
                "Signal ESCALATED: %s (elapsed %dms)",
                result.get("escalate_reason", "unknown"), elapsed,
            )
        else:
            logger.info(
                "Signal: %s (confidence=%.2f, elapsed=%dms)",
                direction, confidence, elapsed,
            )
    except Exception as e:
        logger.error("Signal synthesis failed: %s", e, exc_info=True)


def main():
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    interval_min = int(os.getenv("SIGNAL_INTERVAL_MINUTES", "30"))

    # Trading hours: Mon–Fri 09:00–14:30, every N minutes
    scheduler.add_job(
        _run_signal_synthesis,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="9-14",
            minute=f"0,{interval_min}" if interval_min < 60 else "0",
            timezone="Asia/Shanghai",
        ),
        id="signal_trading",
        name="Signal Agent (trading hours)",
        max_instances=1,
        coalesce=True,
    )

    # Off-hours: every 2 hours
    scheduler.add_job(
        _run_signal_synthesis,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="15,17,19,21,23",
            minute="0",
            timezone="Asia/Shanghai",
        ),
        id="signal_off_hours",
        name="Signal Agent (off-hours)",
        max_instances=1,
        coalesce=True,
    )

    # Run once at startup
    scheduler.add_job(
        _run_signal_synthesis,
        id="signal_startup",
        name="Signal Agent (startup)",
    )

    def _shutdown(signum, frame):
        logger.info("Shutting down signal agent (signal %d)", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start signal HTTP service for SynthesizeSignal / GetLatestSignal
    from src.signal_agent.grpc_service import start_signal_service
    start_signal_service()

    logger.info("Signal agent starting: interval=%dmin", interval_min)
    scheduler.start()


if __name__ == "__main__":
    main()
