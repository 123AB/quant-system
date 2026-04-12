package com.quant.soy.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;

@Data
@Entity
@Table(name = "crush_margin_history")
public class CrushMarginEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "time", nullable = false)
    private Instant time;

    @Column(name = "meal_price")
    private BigDecimal mealPrice;

    @Column(name = "oil_price")
    private BigDecimal oilPrice;

    @Column(name = "cbot_cents")
    private BigDecimal cbotCents;

    private BigDecimal usdcny;

    @Column(name = "freight_usd")
    private BigDecimal freightUsd;

    @Column(name = "landed_cost_cny")
    private BigDecimal landedCostCny;

    @Column(name = "total_revenue_cny")
    private BigDecimal totalRevenueCny;

    @Column(name = "crush_margin_cny")
    private BigDecimal crushMarginCny;

    private String signal;
}
