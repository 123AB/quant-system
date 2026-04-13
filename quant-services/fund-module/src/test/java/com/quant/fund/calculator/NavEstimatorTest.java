package com.quant.fund.calculator;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

class NavEstimatorTest {

    @Test
    void basicEstimation() {
        BigDecimal est = NavEstimator.estimate("1.0000", 1.5);
        assertNotNull(est);
        assertEquals(new BigDecimal("1.0150"), est);
    }

    @Test
    void negativeIndexChange() {
        BigDecimal est = NavEstimator.estimate("2.0000", -2.0);
        assertNotNull(est);
        assertEquals(new BigDecimal("1.9600"), est);
    }

    @Test
    void zeroChange() {
        BigDecimal est = NavEstimator.estimate("1.2345", 0.0);
        assertNotNull(est);
        assertEquals(new BigDecimal("1.2345"), est);
    }

    @Test
    void nullNavReturnsNull() {
        assertNull(NavEstimator.estimate(null, 1.0));
    }

    @Test
    void blankNavReturnsNull() {
        assertNull(NavEstimator.estimate("  ", 1.0));
    }

    @Test
    void invalidNavReturnsNull() {
        assertNull(NavEstimator.estimate("not_a_number", 1.0));
    }

    @Test
    void scalesTo4DecimalPlaces() {
        BigDecimal est = NavEstimator.estimate("1.0000", 0.123);
        assertNotNull(est);
        assertEquals(4, est.scale());
    }
}
