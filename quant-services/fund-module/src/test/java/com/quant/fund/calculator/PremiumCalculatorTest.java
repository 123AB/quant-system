package com.quant.fund.calculator;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

class PremiumCalculatorTest {

    @Test
    void premiumWhenMarketAboveNav() {
        BigDecimal pct = PremiumCalculator.premiumPct(
                new BigDecimal("1.100"), new BigDecimal("1.000"));
        assertNotNull(pct);
        assertEquals(new BigDecimal("10.00"), pct);
    }

    @Test
    void discountWhenMarketBelowNav() {
        BigDecimal pct = PremiumCalculator.premiumPct(
                new BigDecimal("0.900"), new BigDecimal("1.000"));
        assertNotNull(pct);
        assertEquals(new BigDecimal("-10.00"), pct);
    }

    @Test
    void zeroWhenEqual() {
        BigDecimal pct = PremiumCalculator.premiumPct(
                new BigDecimal("1.000"), new BigDecimal("1.000"));
        assertNotNull(pct);
        assertEquals(0, pct.compareTo(BigDecimal.ZERO));
    }

    @Test
    void nullWhenNavIsZero() {
        assertNull(PremiumCalculator.premiumPct(new BigDecimal("1.0"), BigDecimal.ZERO));
    }

    @Test
    void nullWhenNavIsNull() {
        assertNull(PremiumCalculator.premiumPct(new BigDecimal("1.0"), null));
    }

    @Test
    void nullWhenMarketPriceIsNull() {
        assertNull(PremiumCalculator.premiumPct(null, new BigDecimal("1.0")));
    }

    @Test
    void analyzeIntegration() {
        PremiumCalculator.LofPremiumResult r = PremiumCalculator.analyze(
                "164906", "前海开源沪深300指数",
                new BigDecimal("1.050"), "1.0000", 1.5
        );

        assertNotNull(r);
        assertEquals("164906", r.fundCode());
        assertNotNull(r.estimatedNav());
        assertNotNull(r.premiumPct());
        assertEquals("estimated", r.navSource());
    }

    @Test
    void analyzeWithInvalidNav() {
        PremiumCalculator.LofPremiumResult r = PremiumCalculator.analyze(
                "164906", "TestFund",
                new BigDecimal("1.050"), null, 1.5
        );

        assertNull(r.estimatedNav());
        assertNull(r.premiumPct());
        assertEquals("unavailable", r.navSource());
    }
}
