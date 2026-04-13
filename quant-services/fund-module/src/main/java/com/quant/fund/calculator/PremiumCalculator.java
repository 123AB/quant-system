package com.quant.fund.calculator;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * LOF premium/discount calculator — mirrors Python calculator.py calc_premium_pct.
 *
 * Premium = (market_price - est_nav) / est_nav × 100
 * Positive → premium (场内价高于净值), Negative → discount (场内价低于净值)
 */
public final class PremiumCalculator {

    private static final int PCT_SCALE = 2;
    private static final BigDecimal HUNDRED = new BigDecimal("100");

    private PremiumCalculator() {}

    /**
     * @param marketPrice  current market price
     * @param estNav       estimated or official NAV
     * @return premium percentage (2dp), or null if NAV is zero/null
     */
    public static BigDecimal premiumPct(BigDecimal marketPrice, BigDecimal estNav) {
        if (marketPrice == null || estNav == null || estNav.signum() == 0) {
            return null;
        }
        return marketPrice.subtract(estNav)
                .divide(estNav, 10, RoundingMode.HALF_UP)
                .multiply(HUNDRED)
                .setScale(PCT_SCALE, RoundingMode.HALF_UP);
    }

    /**
     * Convenience: full LOF premium analysis.
     */
    public static LofPremiumResult analyze(
            String fundCode, String fundName,
            BigDecimal marketPrice, String t1Nav, double indexChangePct
    ) {
        BigDecimal estNav = NavEstimator.estimate(t1Nav, indexChangePct);
        BigDecimal premium = (estNav != null) ? premiumPct(marketPrice, estNav) : null;

        return new LofPremiumResult(
                fundCode, fundName, marketPrice, estNav,
                premium, indexChangePct,
                estNav != null ? "estimated" : "unavailable"
        );
    }

    public record LofPremiumResult(
            String fundCode,
            String fundName,
            BigDecimal marketPrice,
            BigDecimal estimatedNav,
            BigDecimal premiumPct,
            double indexChangePct,
            String navSource
    ) {}
}
