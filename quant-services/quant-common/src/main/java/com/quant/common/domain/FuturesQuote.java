package com.quant.common.domain;

import com.quant.common.enums.DataQuality;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;

@Data
@Builder
public class FuturesQuote {
    private String symbol;
    private String name;
    private String exchange;
    private BigDecimal open;
    private BigDecimal high;
    private BigDecimal low;
    private BigDecimal close;
    private long volume;
    private BigDecimal amount;
    private BigDecimal changePct;
    private String unit;
    private DataQuality dataQuality;
    private Instant updatedAt;
}
