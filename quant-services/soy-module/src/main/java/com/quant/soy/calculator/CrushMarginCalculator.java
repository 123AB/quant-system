package com.quant.soy.calculator;

import com.quant.common.domain.CrushMarginResult;
import com.quant.common.enums.CrushSignal;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Crush margin calculation — mirrors Python crusher.py with BigDecimal precision.
 *
 * Revenue = meal_price × 78.5% + oil_price × 18.5%
 * Cost    = CBOT_landed + processing_fee
 * Margin  = Revenue - Cost
 */
public final class CrushMarginCalculator {

    private static final BigDecimal MEAL_WEIGHT = new BigDecimal("0.785");
    private static final BigDecimal OIL_WEIGHT = new BigDecimal("0.185");
    private static final BigDecimal BUSHEL_TO_TON = new BigDecimal("36.7437");
    private static final BigDecimal TARIFF_RATE = new BigDecimal("0.03");
    private static final BigDecimal VAT_RATE = new BigDecimal("0.09");
    private static final BigDecimal PORT_MISC = new BigDecimal("100");
    private static final BigDecimal DEFAULT_PROCESSING = new BigDecimal("120");
    private static final int SCALE = 2;

    private CrushMarginCalculator() {}

    public static CrushMarginResult calculate(
            BigDecimal mealPrice,
            BigDecimal oilPrice,
            BigDecimal cbotCents,
            BigDecimal usdcny,
            BigDecimal freightUsd
    ) {
        BigDecimal cbotUsdPerTon = cbotCents
                .divide(new BigDecimal("100"), 6, RoundingMode.HALF_UP)
                .multiply(BUSHEL_TO_TON)
                .setScale(SCALE, RoundingMode.HALF_UP);

        BigDecimal cifUsd = cbotUsdPerTon.add(freightUsd);
        BigDecimal cifCny = cifUsd.multiply(usdcny).setScale(SCALE, RoundingMode.HALF_UP);
        BigDecimal tariff = cifCny.multiply(TARIFF_RATE).setScale(SCALE, RoundingMode.HALF_UP);
        BigDecimal dutiable = cifCny.add(tariff);
        BigDecimal vat = dutiable.multiply(VAT_RATE).setScale(SCALE, RoundingMode.HALF_UP);
        BigDecimal landedCost = cifCny.add(tariff).add(vat).add(PORT_MISC);
        BigDecimal totalBeanCost = landedCost.add(DEFAULT_PROCESSING);

        BigDecimal mealRevenue = mealPrice.multiply(MEAL_WEIGHT).setScale(SCALE, RoundingMode.HALF_UP);
        BigDecimal oilRevenue = oilPrice.multiply(OIL_WEIGHT).setScale(SCALE, RoundingMode.HALF_UP);
        BigDecimal totalRevenue = mealRevenue.add(oilRevenue);
        BigDecimal margin = totalRevenue.subtract(totalBeanCost);

        CrushSignal signal;
        if (margin.compareTo(new BigDecimal("200")) > 0) {
            signal = CrushSignal.RICH;
        } else if (margin.compareTo(new BigDecimal("50")) > 0) {
            signal = CrushSignal.NORMAL;
        } else if (margin.compareTo(BigDecimal.ZERO) > 0) {
            signal = CrushSignal.THIN;
        } else {
            signal = CrushSignal.LOSS;
        }

        return CrushMarginResult.builder()
                .mealPrice(mealPrice)
                .oilPrice(oilPrice)
                .cbotCents(cbotCents)
                .usdcny(usdcny)
                .freightUsd(freightUsd)
                .cbotUsdPerTon(cbotUsdPerTon)
                .cifUsd(cifUsd)
                .cifCny(cifCny)
                .tariffCny(tariff)
                .vatCny(vat)
                .portMiscCny(PORT_MISC)
                .landedCostCny(landedCost)
                .processingFeeCny(DEFAULT_PROCESSING)
                .totalBeanCostCny(totalBeanCost)
                .mealRevenueCny(mealRevenue)
                .oilRevenueCny(oilRevenue)
                .totalRevenueCny(totalRevenue)
                .crushMarginCny(margin)
                .profitable(margin.compareTo(BigDecimal.ZERO) > 0)
                .signal(signal)
                .build();
    }
}
