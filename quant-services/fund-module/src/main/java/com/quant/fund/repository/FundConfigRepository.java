package com.quant.fund.repository;

import com.quant.fund.entity.FundConfigEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface FundConfigRepository extends JpaRepository<FundConfigEntity, Integer> {

    List<FundConfigEntity> findByActiveTrue();

    Optional<FundConfigEntity> findByCode(String code);
}
