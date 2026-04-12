package com.quant.soy.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;

@Data
@Entity
@Table(name = "market_quotes")
public class MarketQuoteEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "time", nullable = false)
    private Instant time;

    private String source;
    private String symbol;

    @Column(name = "\"open\"")
    private BigDecimal open;

    private BigDecimal high;
    private BigDecimal low;

    @Column(name = "\"close\"")
    private BigDecimal close;

    private Long volume;
    private BigDecimal amount;

    @Column(name = "change_pct")
    private BigDecimal changePct;

    @Column(name = "data_quality")
    private String dataQuality;
}
