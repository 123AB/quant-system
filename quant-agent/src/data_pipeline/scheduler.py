"""
APScheduler entry point for the data pipeline.

Schedules:
  - Trading hours (Mon–Fri 09:00–15:00 CST): every 30 seconds
  - Off-hours: every 30 minutes
  - USDA report days: hourly WASDE refresh (TODO: integrate report calendar)

Run: python -m src.data_pipeline.scheduler
"""

import logging
import os
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_pipeline")


def _run_pipeline_job():
    """Job wrapper that imports and runs the pipeline."""
    from src.data_pipeline.workflow_runner import run_pipeline
    try:
        state = run_pipeline()
        logger.info("Pipeline completed: %s", state.current_phase.value)
    except Exception as e:
        logger.error("Pipeline job failed: %s", e)


def main():
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    trading_interval = int(os.getenv("PIPELINE_INTERVAL_TRADING", "30"))
    off_hours_interval = int(os.getenv("PIPELINE_INTERVAL_OFF_HOURS", "1800"))

    # Trading hours: Mon–Fri 09:00–15:00 CST
    scheduler.add_job(
        _run_pipeline_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="9-14",
            second=f"*/{trading_interval}" if trading_interval < 60 else "0",
            minute="*" if trading_interval < 60 else f"*/{trading_interval // 60}",
            timezone="Asia/Shanghai",
        ),
        id="pipeline_trading",
        name="Data Pipeline (trading hours)",
        max_instances=1,
        coalesce=True,
    )

    # Off-hours: every 30 minutes (or configured interval)
    scheduler.add_job(
        _run_pipeline_job,
        trigger=IntervalTrigger(seconds=off_hours_interval),
        id="pipeline_off_hours",
        name="Data Pipeline (off-hours)",
        max_instances=1,
        coalesce=True,
    )

    # Run once at startup
    scheduler.add_job(
        _run_pipeline_job,
        id="pipeline_startup",
        name="Data Pipeline (startup)",
    )

    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler (signal %d)", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info(
        "Scheduler starting: trading=%ds, off-hours=%ds",
        trading_interval, off_hours_interval,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
