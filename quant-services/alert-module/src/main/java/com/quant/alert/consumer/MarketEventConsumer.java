package com.quant.alert.consumer;

import com.quant.alert.entity.AlertRuleEntity;
import com.quant.alert.service.AlertService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.ReadOffset;
import org.springframework.data.redis.connection.stream.StreamOffset;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * Consumes Redis Stream events from data-pipeline and signal-agent,
 * checks alert rules, and publishes matched alerts to quant:ws_push.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MarketEventConsumer {

    private final StringRedisTemplate redis;
    private final AlertService alertService;
    private String lastMarketId = "0";
    private String lastAlertId = "0";

    @Scheduled(fixedDelay = 5000)
    public void consumeMarketEvents() {
        try {
            var records = redis.opsForStream().read(
                    StreamOffset.create("quant:market_events", ReadOffset.from(lastMarketId)));
            if (records == null) return;

            for (var record : records) {
                @SuppressWarnings("unchecked")
                MapRecord<String, Object, Object> mr = (MapRecord<String, Object, Object>) record;
                lastMarketId = mr.getId().getValue();
                processMarketEvent(mr.getValue());
            }
        } catch (Exception e) {
            log.debug("Stream read (market_events): {}", e.getMessage());
        }
    }

    private void processMarketEvent(Map<Object, Object> event) {
        String type = String.valueOf(event.get("type"));
        if (!"market_context_updated".equals(type) && !"signal_updated".equals(type)) {
            return;
        }

        // Read fresh crush margin from Redis
        Map<Object, Object> crush = redis.opsForHash().entries("soy:crush:latest");
        if (crush.containsKey("crush_margin_cny")) {
            BigDecimal margin = new BigDecimal(crush.get("crush_margin_cny").toString());
            List<AlertRuleEntity> matched = alertService.matchRules("crush_margin", margin);
            for (AlertRuleEntity rule : matched) {
                publishWsPush("crush_margin", margin.toPlainString(), rule.getDescription());
            }
        }

        // Check signal alerts
        if ("signal_updated".equals(type)) {
            String direction = String.valueOf(event.getOrDefault("direction", ""));
            String confidence = String.valueOf(event.getOrDefault("confidence", "0"));
            List<AlertRuleEntity> matched = alertService.matchRules("signal_confidence",
                    new BigDecimal(confidence));
            for (AlertRuleEntity rule : matched) {
                publishWsPush("signal", direction + " (conf=" + confidence + ")", rule.getDescription());
            }
        }
    }

    private void publishWsPush(String metric, String value, String description) {
        redis.convertAndSend("quant:ws_push",
                "{\"metric\":\"" + metric + "\",\"value\":\"" + value
                        + "\",\"description\":\"" + description + "\"}");
        log.info("Alert triggered: {} = {} — {}", metric, value, description);
    }
}
