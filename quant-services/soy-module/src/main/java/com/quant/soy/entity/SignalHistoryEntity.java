package com.quant.soy.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;

@Data
@Entity
@Table(name = "signal_history")
public class SignalHistoryEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "time", nullable = false)
    private Instant time;

    @Column(name = "signal_type")
    private String signalType;

    private String direction;

    private BigDecimal confidence;

    @Column(name = "composite_score")
    private Integer compositeScore;

    @Column(columnDefinition = "jsonb")
    private String factors;

    @Column(name = "reasoning_chain", columnDefinition = "jsonb")
    private String reasoningChain;

    private Boolean escalated;

    @Column(name = "escalate_reason")
    private String escalateReason;

    @Column(name = "market_snapshot_id")
    private String marketSnapshotId;
}
