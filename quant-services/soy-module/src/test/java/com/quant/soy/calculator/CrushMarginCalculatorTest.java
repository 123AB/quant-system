package com.quant.soy.calculator;

import com.quant.common.domain.CrushMarginResult;
import com.quant.common.enums.CrushSignal;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

class CrushMarginCalculatorTest {

    private static final BigDecimal FREIGHT = new BigDecimal("45");

    @Test
    void profitableScenario() {
        CrushMarginResult r = CrushMarginCalculator.calculate(
                new BigDecimal("3800"),  // meal
                new BigDecimal("8200"),  // oil
                new BigDecimal("1100"),  // CBOT cents/bushel
                new BigDecimal("7.25"),  // USD/CNY
                FREIGHT
        );

        assertNotNull(r);
        assertTrue(r.getCbotUsdPerTon().compareTo(BigDecimal.ZERO) > 0, "CBOT USD/ton should be positive");
        assertTrue(r.getCifCny().compareTo(BigDecimal.ZERO) > 0, "CIF CNY should be positive");
        assertTrue(r.getTariffCny().compareTo(BigDecimal.ZERO) > 0, "Tariff should be positive");
        assertTrue(r.getVatCny().compareTo(BigDecimal.ZERO) > 0, "VAT should be positive");
        assertEquals(new BigDecimal("100"), r.getPortMiscCny());
        assertEquals(new BigDecimal("120"), r.getProcessingFeeCny());
        assertNotNull(r.getSignal());
    }

    @Test
    void lossScenario() {
        CrushMarginResult r = CrushMarginCalculator.calculate(
                new BigDecimal("2800"),  // cheap meal
                new BigDecimal("5000"),  // cheap oil
                new BigDecimal("1800"),  // expensive CBOT
                new BigDecimal("7.50"),  // weaker CNY
                FREIGHT
        );

        assertNotNull(r);
        assertFalse(r.isProfitable());
        assertEquals(CrushSignal.LOSS, r.getSignal());
        assertTrue(r.getCrushMarginCny().compareTo(BigDecimal.ZERO) < 0);
    }

    @Test
    void richSignalWhenMarginAbove200() {
        CrushMarginResult r = CrushMarginCalculator.calculate(
                new BigDecimal("4200"),
                new BigDecimal("9500"),
                new BigDecimal("900"),
                new BigDecimal("7.10"),
                FREIGHT
        );

        assertTrue(r.isProfitable());
        if (r.getCrushMarginCny().compareTo(new BigDecimal("200")) > 0) {
            assertEquals(CrushSignal.RICH, r.getSignal());
        }
    }

    @Test
    void revenueBreakdown() {
        BigDecimal meal = new BigDecimal("3500");
        BigDecimal oil = new BigDecimal("8000");
        CrushMarginResult r = CrushMarginCalculator.calculate(meal, oil, new BigDecimal("1000"), new BigDecimal("7.25"), FREIGHT);

        BigDecimal expectedMealRev = meal.multiply(new BigDecimal("0.785")).setScale(2, java.math.RoundingMode.HALF_UP);
        BigDecimal expectedOilRev = oil.multiply(new BigDecimal("0.185")).setScale(2, java.math.RoundingMode.HALF_UP);

        assertEquals(expectedMealRev, r.getMealRevenueCny());
        assertEquals(expectedOilRev, r.getOilRevenueCny());
        assertEquals(expectedMealRev.add(expectedOilRev), r.getTotalRevenueCny());
    }
}
