"""
Import soybean crush margin calculator.

Pure calculation — no framework dependencies.
Uses Decimal for financial precision.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

MEAL_YIELD = Decimal("0.785")
OIL_YIELD = Decimal("0.185")
BUSHELS_PER_TON = Decimal("36.744")
TARIFF_RATE = Decimal("0.03")
VAT_RATE = Decimal("0.09")
PORT_MISC = Decimal("70")
DEFAULT_PROCESSING = Decimal("120")
EXPORT_PREMIUM = Decimal("10")


def _d(v) -> Decimal:
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return Decimal("0")


def landed_cost(
    cbot_cents: float,
    freight_usd: float,
    usdcny: float,
    processing_fee: float | None = None,
) -> dict:
    """Calculate total import landed cost for 1 metric ton of soybeans (CNY/ton)."""
    cbot_usd_ton = _d(cbot_cents) / Decimal("100") * BUSHELS_PER_TON
    freight = _d(freight_usd)
    rate = _d(usdcny)
    proc = _d(processing_fee) if processing_fee else DEFAULT_PROCESSING

    fob_usd = cbot_usd_ton + EXPORT_PREMIUM
    insurance = (fob_usd + freight) * Decimal("0.001")
    cif_usd = fob_usd + freight + insurance
    cif_cny = cif_usd * rate
    tariff = cif_cny * TARIFF_RATE
    dutiable = cif_cny + tariff
    vat = dutiable * VAT_RATE
    landed = (dutiable + vat + PORT_MISC).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "cbot_usd_per_ton": float(cbot_usd_ton.quantize(Decimal("0.01"))),
        "freight_usd": float(freight),
        "cif_usd": float(cif_usd.quantize(Decimal("0.01"))),
        "cif_cny": float(cif_cny.quantize(Decimal("0.01"))),
        "tariff_cny": float(tariff.quantize(Decimal("0.01"))),
        "vat_cny": float(vat.quantize(Decimal("0.01"))),
        "port_misc_cny": float(PORT_MISC),
        "landed_cost_cny": float(landed),
        "processing_fee_cny": float(proc),
        "total_bean_cost_cny": float((landed + proc).quantize(Decimal("0.01"))),
    }


def crush_margin(
    meal_price: float,
    oil_price: float,
    bean_total_cost: float,
) -> dict:
    """Calculate crush margin (CNY per ton of bean processed)."""
    meal_rev = _d(meal_price) * MEAL_YIELD
    oil_rev = _d(oil_price) * OIL_YIELD
    revenue = (meal_rev + oil_rev).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cost = _d(bean_total_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    margin = (revenue - cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "meal_revenue_cny": float(meal_rev.quantize(Decimal("0.01"))),
        "oil_revenue_cny": float(oil_rev.quantize(Decimal("0.01"))),
        "total_revenue_cny": float(revenue),
        "bean_cost_cny": float(cost),
        "crush_margin_cny": float(margin),
        "is_profitable": margin > 0,
        "signal": _signal(float(margin)),
    }


def basis(spot_price: float, futures_price: float) -> dict:
    """Calculate basis = spot - futures."""
    b = _d(spot_price) - _d(futures_price)
    b_f = float(b.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "spot": spot_price,
        "futures": futures_price,
        "basis": b_f,
        "basis_pct": round(b_f / futures_price * 100, 2) if futures_price else None,
        "type": "backwardation" if b_f > 0 else "contango",
    }


def full_crush_analysis(
    meal_price_cny: float,
    oil_price_cny: float,
    cbot_cents: float,
    usdcny: float,
    freight_usd: float = 45.0,
) -> dict:
    """One-shot full crush margin analysis combining landed cost + crush margin."""
    lc = landed_cost(cbot_cents, freight_usd, usdcny)
    bean_cost = lc["total_bean_cost_cny"]
    cm = crush_margin(meal_price_cny, oil_price_cny, bean_cost)
    return {
        "inputs": {
            "meal_price_cny": meal_price_cny,
            "oil_price_cny": oil_price_cny,
            "cbot_cents_per_bushel": cbot_cents,
            "usdcny": usdcny,
            "freight_usd_per_ton": freight_usd,
        },
        "landed_cost": lc,
        "crush": cm,
        "signal": cm["signal"],
    }


def _signal(margin: float) -> str:
    if margin > 200:
        return "rich"
    elif margin > 50:
        return "normal"
    elif margin >= 0:
        return "thin"
    else:
        return "loss"
