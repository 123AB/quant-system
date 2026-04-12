package com.quant.biz.controller;

import com.quant.alert.entity.AlertRuleEntity;
import com.quant.alert.service.AlertService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/alert")
@RequiredArgsConstructor
public class AlertController {

    private final AlertService alertService;

    @PostMapping("/rules")
    public AlertRuleEntity createRule(@RequestBody Map<String, Object> body) {
        return alertService.createRule(
                ((Number) body.get("user_id")).longValue(),
                (String) body.get("metric"),
                (String) body.get("operator"),
                new BigDecimal(body.get("threshold").toString()),
                (String) body.get("channel"),
                (String) body.get("description")
        );
    }

    @GetMapping("/rules")
    public List<AlertRuleEntity> listRules(
            @RequestParam long userId,
            @RequestParam(defaultValue = "true") boolean activeOnly) {
        return alertService.listRules(userId, activeOnly);
    }

    @DeleteMapping("/rules/{ruleId}")
    public Map<String, Boolean> deleteRule(
            @PathVariable int ruleId,
            @RequestParam long userId) {
        alertService.deleteRule(ruleId, userId);
        return Map.of("success", true);
    }
}
