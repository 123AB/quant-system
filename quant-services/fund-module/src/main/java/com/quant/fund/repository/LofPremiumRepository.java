package com.quant.fund.repository;

import com.quant.fund.entity.LofPremiumEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.List;

public interface LofPremiumRepository extends JpaRepository<LofPremiumEntity, Long> {

    List<LofPremiumEntity> findByFundCodeAndTimeAfterOrderByTimeDesc(String fundCode, Instant since);
}
