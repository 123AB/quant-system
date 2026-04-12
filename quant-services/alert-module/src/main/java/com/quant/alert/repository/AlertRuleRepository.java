package com.quant.alert.repository;

import com.quant.alert.entity.AlertRuleEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface AlertRuleRepository extends JpaRepository<AlertRuleEntity, Integer> {

    List<AlertRuleEntity> findByUserId(Long userId);

    List<AlertRuleEntity> findByUserIdAndActiveTrue(Long userId);

    List<AlertRuleEntity> findByMetricAndActiveTrue(String metric);
}
