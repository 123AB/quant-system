package com.quant.common.domain;

import com.quant.common.enums.CrushSignal;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Builder
public class CrushMarginResult {
    private BigDecimal mealPrice;
    private BigDecimal oilPrice;
    private BigDecimal cbotCents;
    private BigDecimal usdcny;
    private BigDecimal freightUsd;

    private BigDecimal cbotUsdPerTon;
    private BigDecimal cifUsd;
    private BigDecimal cifCny;
    private BigDecimal tariffCny;
    private BigDecimal vatCny;
    private BigDecimal portMiscCny;
    private BigDecimal landedCostCny;
    private BigDecimal processingFeeCny;
    private BigDecimal totalBeanCostCny;

    private BigDecimal mealRevenueCny;
    private BigDecimal oilRevenueCny;
    private BigDecimal totalRevenueCny;
    private BigDecimal crushMarginCny;

    private boolean profitable;
    private CrushSignal signal;
}
