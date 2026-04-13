package com.quant.fund.calculator;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * NAV estimator — mirrors Python calculator.py calc_estimated_nav.
 *
 * Estimated NAV = T-1 NAV × (1 + index_change_pct / 100)
 * Rounded to 4 decimal places (standard for Chinese fund NAV).
 */
public final class NavEstimator {

    private static final int NAV_SCALE = 4;
    private static final BigDecimal HUNDRED = new BigDecimal("100");

    private NavEstimator() {}

    /**
     * @param t1Nav           T-1 official NAV, e.g. "1.2345"
     * @param indexChangePct  today's benchmark index change %, e.g. 1.50
     * @return estimated NAV rounded to 4dp, or null on invalid input
     */
    public static BigDecimal estimate(String t1Nav, double indexChangePct) {
        if (t1Nav == null || t1Nav.isBlank()) return null;
        try {
            BigDecimal nav = new BigDecimal(t1Nav);
            BigDecimal change = BigDecimal.valueOf(indexChangePct).divide(HUNDRED, 10, RoundingMode.HALF_UP);
            BigDecimal est = nav.multiply(BigDecimal.ONE.add(change));
            return est.setScale(NAV_SCALE, RoundingMode.HALF_UP);
        } catch (NumberFormatException | ArithmeticException e) {
            return null;
        }
    }
}
