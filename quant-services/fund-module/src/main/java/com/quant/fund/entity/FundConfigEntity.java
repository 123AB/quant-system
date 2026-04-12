package com.quant.fund.entity;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "fund_config")
public class FundConfigEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, unique = true, length = 10)
    private String code;

    @Column(nullable = false)
    private String name;

    private String exchange;

    @Column(name = "index_sina")
    private String indexSina;

    @Column(name = "index_name")
    private String indexName;

    @Column(name = "is_active", nullable = false)
    private boolean active;
}
