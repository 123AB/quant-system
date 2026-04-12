package com.quant.alert.service;

import com.quant.alert.entity.AlertRuleEntity;
import com.quant.alert.repository.AlertRuleRepository;
import com.quant.common.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class AlertService {

    private final AlertRuleRepository ruleRepo;

    public AlertRuleEntity createRule(Long userId, String metric, String operator,
                                      BigDecimal threshold, String channel, String description) {
        var rule = new AlertRuleEntity();
        rule.setUserId(userId);
        rule.setMetric(metric);
        rule.setOperator(operator);
        rule.setThreshold(threshold);
        rule.setChannel(channel != null ? channel : "websocket");
        rule.setDescription(description);
        return ruleRepo.save(rule);
    }

    public List<AlertRuleEntity> listRules(Long userId, boolean activeOnly) {
        return activeOnly ? ruleRepo.findByUserIdAndActiveTrue(userId) : ruleRepo.findByUserId(userId);
    }

    public void deleteRule(int ruleId, long userId) {
        var rule = ruleRepo.findById(ruleId)
                .orElseThrow(() -> new BusinessException("NOT_FOUND", "Alert rule not found"));
        if (rule.getUserId() != userId) {
            throw new BusinessException("FORBIDDEN", "Cannot delete another user's rule");
        }
        ruleRepo.delete(rule);
    }

    /**
     * Check a metric value against all active rules for that metric.
     * Returns matched rules.
     */
    public List<AlertRuleEntity> matchRules(String metric, BigDecimal value) {
        List<AlertRuleEntity> rules = ruleRepo.findByMetricAndActiveTrue(metric);
        return rules.stream()
                .filter(rule -> matches(rule.getOperator(), value, rule.getThreshold()))
                .peek(rule -> {
                    rule.setLastTriggeredAt(Instant.now());
                    ruleRepo.save(rule);
                })
                .toList();
    }

    private boolean matches(String operator, BigDecimal value, BigDecimal threshold) {
        return switch (operator) {
            case "gt", ">" -> value.compareTo(threshold) > 0;
            case "lt", "<" -> value.compareTo(threshold) < 0;
            case "gte", ">=" -> value.compareTo(threshold) >= 0;
            case "lte", "<=" -> value.compareTo(threshold) <= 0;
            case "abs_gt" -> value.abs().compareTo(threshold) > 0;
            default -> false;
        };
    }
}
