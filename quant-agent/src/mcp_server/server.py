"""
MCP Server for soybean research tools.

Exposes 6 tools + 2 resources for Cursor IDE (stdio) or signal-agent (shared code).

Run: python -m src.mcp_server.server
"""

from datetime import datetime, timezone, timedelta
from mcp.server.fastmcp import FastMCP

from src.fetchers import (
    fetch_dce_futures,
    fetch_cbot_soybeans,
    fetch_usdcny,
    fetch_usda_world_psd,
    fetch_usda_china_imports,
    fetch_cot,
)
from src.crusher import landed_cost, crush_margin, full_crush_analysis
from src.validators import validate_all
from src.factor_signal import compute_signal

app = FastMCP("soybean-research")

_CST = timezone(timedelta(hours=8))


def _now_cst() -> str:
    return datetime.now(_CST).isoformat()


# ─── Tool 1: DCE Futures ────────────────────────────────────────────────────

@app.tool()
def get_dce_futures(
    contracts: list[str] = ["M", "Y", "A"],
    include_change: bool = True,
) -> dict:
    """
    获取大连商品交易所豆粕(M)、豆油(Y)、黄大豆一号(A)主力合约实时行情。

    返回每个合约的最新价、开盘价、最高价、最低价、成交量、涨跌幅。
    数据来源：akshare (Sina Finance)。
    """
    quotes_raw = fetch_dce_futures(contracts)
    quotes = {}
    for q in quotes_raw:
        entry = {
            "close": q["close"],
            "open": q["open"],
            "high": q["high"],
            "low": q["low"],
            "volume": q["volume"],
            "unit": q["unit"],
            "name": q["name"],
        }
        if include_change:
            entry["change_pct"] = q["change_pct"]
            entry["change"] = q["change"]
        quotes[q["symbol"]] = entry
    return {
        "quotes": quotes,
        "timestamp": _now_cst(),
        "data_quality": "live",
    }


# ─── Tool 2: Crush Margin ──────────────────────────────────────────────────

@app.tool()
def get_crush_margin(freight_usd: float = 45.0) -> dict:
    """
    计算当前进口大豆压榨利润（元/吨）。

    公式：
    - 收入 = 豆粕价 × 78.5% + 豆油价 × 18.5%
    - 成本 = CBOT大豆到港完税成本（含关税3%、增值税9%、港杂费70元/吨）+ 加工费120元/吨
    - 利润 = 收入 - 成本

    信号含义：rich(>200) 利润丰厚→供应增加；normal(50-200) 正常；
    thin(0-50) 微利→采购谨慎；loss(<0) 亏损→供应收缩→利多豆粕
    """
    dce = fetch_dce_futures(["M", "Y"])
    cbot = fetch_cbot_soybeans()
    usdcny = fetch_usdcny()

    prices = {q["symbol"]: q["close"] for q in dce}
    meal = prices.get("M0", 0)
    oil = prices.get("Y0", 0)
    cbot_cents = cbot["close"] if cbot else 0

    if not all([meal, oil, cbot_cents, usdcny]):
        missing = []
        if not meal: missing.append("豆粕(M)")
        if not oil: missing.append("豆油(Y)")
        if not cbot_cents: missing.append("CBOT美豆")
        if not usdcny: missing.append("USD/CNY")
        return {"error": f"数据不全: {', '.join(missing)}", "timestamp": _now_cst()}

    result = full_crush_analysis(meal, oil, cbot_cents, usdcny, freight_usd)
    result["timestamp"] = _now_cst()
    return result


# ─── Tool 3: USDA Supply/Demand ────────────────────────────────────────────

@app.tool()
def get_usda_supply_demand(region: str = "world") -> dict:
    """
    获取 USDA 全球/中国大豆供需平衡表。

    包含：产量、进口量、压榨量、期末库存、库消比。
    数据来源：USDA FAS PSD Online API（6小时缓存建议）。

    region: "world" = 全球平衡表，"china" = 中国进口数据
    """
    if region == "china":
        data = fetch_usda_china_imports()
        return {"china_imports": data, "source": "USDA FAS PSD Online", "unit": "千吨", "timestamp": _now_cst()}
    else:
        data = fetch_usda_world_psd()
        return {"world_balance": data, "source": "USDA FAS PSD Online", "unit": "千吨(MMT)", "timestamp": _now_cst()}


# ─── Tool 4: COT Positioning ───────────────────────────────────────────────

@app.tool()
def get_cot_positioning() -> dict:
    """
    获取 CFTC 大豆期货持仓报告（Commitments of Traders）。

    包含：非商业多头/空头/净持仓、豆粕多头/空头/净持仓。
    每周五发布，建议24小时缓存。

    关键指标：净持仓变化可反映大资金动向。
    """
    data = fetch_cot()
    data["timestamp"] = _now_cst()
    data["source"] = "CFTC via akshare"
    return data


# ─── Tool 5: Factor Signal ─────────────────────────────────────────────────

@app.tool()
def get_factor_signal() -> dict:
    """
    获取量化因子合成信号。基于 8 个因子的加权评分：

    1. 支撑距离 - 当前价格与关键支撑位的距离
    2. 量能底部 - 成交量相对 5 日均量的倍数
    3. 内外盘背离 - 国内涨幅 vs CBOT 涨幅
    4. 滞后背离确认 - 前一日的内外盘背离
    5. 季节性 - 历史同期的涨跌规律
    6. 基差变化(5日) - 现货-期货基差的 5 日变化
    7. 开机率变化 - 油厂开机率的 5 日变化
    8. 现货基差 - 当前现货-期货基差水平

    返回：方向（做多/观望/做空）、置信度、各因子明细得分。
    """
    result = compute_signal()
    result["timestamp"] = _now_cst()
    return result


# ─── Tool 6: Data Quality Validation ───────────────────────────────────────

@app.tool()
def validate_data_quality() -> dict:
    """
    执行多源交叉验证，检查当前数据是否可靠：

    1. DCE 行情：akshare 主力合约收盘价 vs 历史数据（偏差 >10% = 异常）
    2. USD/CNY：akshare 汇率 vs 中国银行中间价（偏差 >0.5% = 警告）
    3. 压榨利润：计算结果 vs 历史区间 [-300, +600]（超出 = 警告）

    返回每项验证的状态（ok/warning/error）和具体偏差数据。
    """
    dce = fetch_dce_futures(["M", "Y", "A"])
    usdcny = fetch_usdcny()

    crush_val = None
    prices = {q["symbol"]: q["close"] for q in dce}
    meal = prices.get("M0", 0)
    oil = prices.get("Y0", 0)
    cbot = fetch_cbot_soybeans()
    cbot_cents = cbot["close"] if cbot else 0
    if all([meal, oil, cbot_cents, usdcny]):
        lc = landed_cost(cbot_cents, 45.0, usdcny)
        cm = crush_margin(meal, oil, lc["total_bean_cost_cny"])
        crush_val = cm["crush_margin_cny"]

    results = validate_all(dce, usdcny, crush_val)
    return {"validations": results, "timestamp": _now_cst()}


# ─── Resource 1: Crush Formula ─────────────────────────────────────────────

@app.resource("quant://crush-formula")
def crush_formula() -> str:
    """进口大豆压榨利润完整计算公式"""
    return """# 进口大豆压榨利润计算

## 成本端
- CBOT 美分/蒲 → USD/吨: price_cents / 100 × 36.744
- FOB = CBOT_USD/吨 + 升水 10 USD
- CIF = FOB + 海运费 + 保险(0.1%)
- 到港价(CNY) = CIF × USD/CNY
- 关税 = 到港价 × 3%
- 增值税 = (到港价 + 关税) × 9%
- 港杂费 = 70 元/吨
- 加工费 = 120 元/吨
- 总成本 = 到港价 + 关税 + 增值税 + 港杂费 + 加工费

## 收入端
- 豆粕收入 = 豆粕价 × 78.5% (出粕率)
- 豆油收入 = 豆油价 × 18.5% (出油率)
- 总收入 = 豆粕收入 + 豆油收入

## 利润
- 压榨利润 = 总收入 - 总成本

## 信号
- > 200 元/吨: rich (利润丰厚, 油厂扩大开机, 豆粕供应增加)
- 50-200: normal (正常盈利)
- 0-50: thin (微利, 油厂谨慎采购)
- < 0: loss (亏损压榨, 供应收缩, 利多豆粕)"""


# ─── Resource 2: Analyst Rules ─────────────────────────────────────────────

@app.resource("quant://analyst-rules")
def analyst_rules() -> str:
    """wn170411 分析师决策框架"""
    return """# wn170411 分析师决策框架

## 核心规则（从 34 篇研报中提取）

1. 价格触及支撑位 + 成交量突增 → 底部确认，分批建多头仓位
2. 自底部累涨 1000–1200 元/吨 → 分批减仓离场，不追高
3. 美豆大跌但国内不跟 → 国内内生强势，维持多头
4. 6–9月 09合约季节性偏多，历史从未持续下跌

## 关键价格位（出现频次 ≥5 次）
3000, 3200, 3300, 3400, 3600, 3800, 4000, 4300 元/吨

## 8 因子打分体系
| 因子 | 做多条件 | 做空条件 |
|------|---------|---------|
| 支撑距离 | 跌破支撑 2% | 远离支撑 |
| 量能底部 | 成交量 >1.5x 均量 (近支撑时) | - |
| 内外盘背离 | 国内涨幅 > CBOT +0.2% | - |
| 滞后背离 | 前日也跑赢 | - |
| 季节性 | 6-9月 | 2月南美丰收 |
| 基差变化5日 | 基差收窄 >20元 | 基差走扩 >20元 |
| 开机率变化 | 开机率下降 >0.5% | - |"""


if __name__ == "__main__":
    app.run()
