"""
Fund data pipeline — periodically fetches LOF prices, NAVs, index changes,
calculates estimated NAV and premium, and writes to Redis.

Redis key per fund: fund:data:{code} (Hash)
Redis key for full list: fund:all_codes (Set)

Run: python -m src.fund_pipeline.main
"""

import logging
import os
import signal
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import psycopg
import redis
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.fund_pipeline.fetchers import fetch_lof_prices, fetch_index_changes, fetch_navs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fund_pipeline")

_NAV_PLACES = Decimal("0.0001")
_PCT_PLACES = Decimal("0.01")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant_dev_2026@localhost:5432/quant")
FUND_TTL = int(os.getenv("FUND_DATA_TTL", "120"))


def _calc_estimated_nav(t1_nav_str: str, index_change_pct: float) -> str | None:
    try:
        nav = Decimal(str(t1_nav_str))
        change = Decimal(str(index_change_pct)) / Decimal("100")
        est = nav * (Decimal("1") + change)
        return str(est.quantize(_NAV_PLACES, rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def _calc_premium_pct(market_price: float, est_nav_str: str) -> str | None:
    try:
        price = Decimal(str(market_price))
        est_nav = Decimal(est_nav_str)
        if est_nav == 0:
            return None
        premium = (price - est_nav) / est_nav * Decimal("100")
        return str(premium.quantize(_PCT_PLACES, rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def _load_fund_configs() -> list[dict]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code, name, exchange, index_sina, index_name "
                "FROM fund_config WHERE is_active = true"
            )
            rows = cur.fetchall()
    return [
        {"code": r[0], "name": r[1], "exchange": r[2], "index_sina": r[3], "index_name": r[4]}
        for r in rows
    ]


def _today_cn() -> str:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def _now_cn() -> str:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def run_fund_pipeline():
    """Main pipeline job: fetch all data, compute, write to Redis."""
    rdb = redis.from_url(REDIS_URL, decode_responses=True)

    fund_configs = _load_fund_configs()
    if not fund_configs:
        logger.warning("No active funds in fund_config table")
        return

    codes = [fc["code"] for fc in fund_configs]
    unique_indices = list({fc["index_sina"] for fc in fund_configs})

    logger.info("Fetching data for %d funds, %d indices", len(codes), len(unique_indices))

    prices = fetch_lof_prices(fund_configs)
    navs = fetch_navs(codes)
    indices = fetch_index_changes(unique_indices)

    now = _now_cn()
    today = _today_cn()
    pipe = rdb.pipeline()
    written = 0

    for fc in fund_configs:
        code = fc["code"]
        price_data = prices.get(code, {})
        nav_data = navs.get(code, {})
        index_data = indices.get(fc["index_sina"], {})

        t1_nav = nav_data.get("nav", "")
        nav_date = nav_data.get("nav_date", "")
        index_change_pct = index_data.get("change_pct")

        # Smart NAV resolution
        if nav_date == today and t1_nav:
            display_nav = t1_nav
            nav_type = "official_t0"
        elif t1_nav and index_change_pct is not None:
            display_nav = _calc_estimated_nav(t1_nav, index_change_pct)
            nav_type = "estimated"
        else:
            display_nav = None
            nav_type = ""

        # Premium calculation
        market_price = price_data.get("price")
        premium_pct = None
        if display_nav and market_price:
            premium_pct = _calc_premium_pct(market_price, display_nav)

        data = {
            "code": code,
            "name": fc["name"],
            "exchange": fc["exchange"],
            "price": str(price_data.get("price", "")),
            "prev_close": str(price_data.get("prev_close", "")),
            "change_pct": str(price_data.get("change_pct", "")),
            "volume_wan": str(price_data.get("volume_wan", "")),
            "open": str(price_data.get("open", "")),
            "high": str(price_data.get("high", "")),
            "low": str(price_data.get("low", "")),
            "t1_nav": t1_nav or "",
            "nav_date": nav_date or "",
            "display_nav": str(display_nav) if display_nav else "",
            "nav_type": nav_type or "",
            "index_sina": fc["index_sina"],
            "index_name": fc["index_name"],
            "index_change_pct": str(index_change_pct) if index_change_pct is not None else "",
            "premium_pct": premium_pct if premium_pct is not None else "",
            "updated_at": now,
        }

        key = f"fund:data:{code}"
        pipe.hset(key, mapping=data)
        pipe.expire(key, FUND_TTL)
        pipe.sadd("fund:all_codes", code)
        written += 1

    pipe.expire("fund:all_codes", FUND_TTL)
    pipe.execute()
    rdb.close()

    price_cnt = len(prices)
    nav_cnt = len(navs)
    logger.info(
        "Fund pipeline done: %d funds written, %d prices, %d NAVs fetched",
        written, price_cnt, nav_cnt,
    )


def main():
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    trading_interval = int(os.getenv("FUND_INTERVAL_TRADING", "30"))
    off_hours_interval = int(os.getenv("FUND_INTERVAL_OFF_HOURS", "300"))

    scheduler.add_job(
        run_fund_pipeline,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            second=f"*/{trading_interval}" if trading_interval < 60 else "0",
            minute="*" if trading_interval < 60 else f"*/{trading_interval // 60}",
            timezone="Asia/Shanghai",
        ),
        id="fund_trading",
        name="Fund Pipeline (trading hours)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        run_fund_pipeline,
        trigger=IntervalTrigger(seconds=off_hours_interval),
        id="fund_off_hours",
        name="Fund Pipeline (off-hours)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        run_fund_pipeline,
        id="fund_startup",
        name="Fund Pipeline (startup)",
    )

    def _shutdown(signum, frame):
        logger.info("Shutting down fund pipeline (signal %d)", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info(
        "Fund pipeline starting: trading=%ds, off-hours=%ds",
        trading_interval, off_hours_interval,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
