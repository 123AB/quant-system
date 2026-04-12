package com.quant.fund.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;

@Data
@Entity
@Table(name = "lof_premium_history")
public class LofPremiumEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "time", nullable = false)
    private Instant time;

    @Column(name = "fund_code", nullable = false)
    private String fundCode;

    @Column(name = "market_price")
    private BigDecimal marketPrice;

    @Column(name = "estimated_nav")
    private BigDecimal estimatedNav;

    @Column(name = "official_nav")
    private BigDecimal officialNav;

    @Column(name = "premium_pct")
    private BigDecimal premiumPct;

    @Column(name = "index_change_pct")
    private BigDecimal indexChangePct;

    @Column(name = "nav_source")
    private String navSource;
}
