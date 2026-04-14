package com.quant.soy.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quant.common.domain.CrushMarginResult;
import com.quant.common.domain.FuturesQuote;
import com.quant.common.enums.DataQuality;
import com.quant.soy.calculator.CrushMarginCalculator;
import com.quant.soy.entity.MarketQuoteEntity;
import com.quant.soy.repository.CrushMarginRepository;
import com.quant.soy.repository.MarketQuoteRepository;
import com.quant.soy.repository.SignalHistoryRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class SoyService {

    private final StringRedisTemplate redis;
    private final MarketQuoteRepository quoteRepo;
    private final CrushMarginRepository crushRepo;
    private final SignalHistoryRepository signalRepo;
    private final ObjectMapper objectMapper;

    /**
     * Read DCE futures from Redis (written by Python data-pipeline).
     */
    public List<FuturesQuote> getDceFutures() {
        List<FuturesQuote> quotes = new ArrayList<>();
        for (String sym : List.of("M0", "Y0", "A0")) {
            Map<Object, Object> data = redis.opsForHash().entries("soy:dce:" + sym);
            if (!data.isEmpty()) {
                quotes.add(FuturesQuote.builder()
                        .symbol(sym)
                        .name(str(data.get("name")))
                        .exchange("DCE")
                        .open(bd(data.get("open")))
                        .high(bd(data.get("high")))
                        .low(bd(data.get("low")))
                        .close(bd(data.get("close")))
                        .volume(lng(data.get("volume")))
                        .changePct(bd(data.get("change_pct")))
                        .unit(str(data.get("unit")))
                        .dataQuality(DataQuality.LIVE)
                        .updatedAt(Instant.now())
                        .build());
            }
        }
        return quotes;
    }

    /**
     * Compute crush margin using latest cached data.
     */
    public CrushMarginResult getCrushMargin(BigDecimal freightUsd) {
        List<FuturesQuote> futures = getDceFutures();
        BigDecimal meal = futures.stream()
                .filter(f -> "M0".equals(f.getSymbol()))
                .findFirst().map(FuturesQuote::getClose).orElse(BigDecimal.ZERO);
        BigDecimal oil = futures.stream()
                .filter(f -> "Y0".equals(f.getSymbol()))
                .findFirst().map(FuturesQuote::getClose).orElse(BigDecimal.ZERO);

        Map<Object, Object> cbot = redis.opsForHash().entries("soy:cbot:latest");
        BigDecimal cbotCents = bd(cbot.get("close"));

        String usdcnyStr = redis.opsForValue().get("soy:fx:usdcny");
        BigDecimal usdcny = usdcnyStr != null ? new BigDecimal(usdcnyStr) : new BigDecimal("7.25");

        return CrushMarginCalculator.calculate(meal, oil, cbotCents, usdcny, freightUsd);
    }

    /**
     * Read historical quotes from TimescaleDB.
     */
    public List<MarketQuoteEntity> getHistory(String symbol, int days) {
        Instant since = Instant.now().minus(days, ChronoUnit.DAYS);
        return quoteRepo.findRecentBySymbol(symbol, since, days * 48);
    }

    /**
     * Read COT positioning from Redis (written by Python data-pipeline).
     */
    public Map<String, Object> getCot() {
        Map<Object, Object> raw = redis.opsForHash().entries("soy:cot:latest");
        if (raw.isEmpty()) return Map.of("cot", Map.of());
        Map<String, Object> cot = new LinkedHashMap<>();
        for (var entry : raw.entrySet()) {
            String key = entry.getKey().toString();
            String val = entry.getValue().toString();
            cot.put(key, parseValue(val));
        }
        return Map.of("cot", cot);
    }

    /**
     * Read USDA world soybean supply/demand from Redis.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getWasde() {
        String json = redis.opsForValue().get("soy:usda:world");
        if (json == null || json.isBlank()) return Map.of("wasde", Map.of());
        try {
            Map<String, Object> data = objectMapper.readValue(json, Map.class);
            return Map.of("wasde", data);
        } catch (Exception e) {
            log.warn("Failed to parse USDA world data: {}", e.getMessage());
            return Map.of("wasde", Map.of(), "error", e.getMessage());
        }
    }

    /**
     * Read USDA China imports from Redis.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getChinaImports() {
        String json = redis.opsForValue().get("soy:usda:china");
        if (json == null || json.isBlank()) return Map.of("china_imports", List.of());
        try {
            List<Object> data = objectMapper.readValue(json, List.class);
            return Map.of("china_imports", data);
        } catch (Exception e) {
            log.warn("Failed to parse USDA China data: {}", e.getMessage());
            return Map.of("china_imports", List.of(), "error", e.getMessage());
        }
    }

    /**
     * Read DCE warehouse inventory from Redis.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getInventory() {
        String json = redis.opsForValue().get("soy:inventory:latest");
        if (json == null || json.isBlank()) return Map.of("inventory", Map.of());
        try {
            Map<String, Object> data = objectMapper.readValue(json, Map.class);
            return Map.of("inventory", data);
        } catch (Exception e) {
            log.warn("Failed to parse inventory data: {}", e.getMessage());
            return Map.of("inventory", Map.of(), "error", e.getMessage());
        }
    }

    /**
     * Read factor signal from Redis.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getFactorSignal() {
        String json = redis.opsForValue().get("soy:factor_signal:latest");
        if (json == null || json.isBlank()) return Map.of("signal", Map.of());
        try {
            Map<String, Object> data = objectMapper.readValue(json, Map.class);
            return data;
        } catch (Exception e) {
            log.warn("Failed to parse factor signal: {}", e.getMessage());
            return Map.of("signal", Map.of(), "error", e.getMessage());
        }
    }

    /**
     * Clear all soy-related Redis caches.
     */
    public List<String> refreshCache() {
        List<String> cleared = new ArrayList<>();
        Set<String> keys = redis.keys("soy:*");
        if (keys != null && !keys.isEmpty()) {
            redis.delete(keys);
            cleared.addAll(keys);
        }
        return cleared;
    }

    private static Object parseValue(String val) {
        if (val == null) return null;
        try { return Long.parseLong(val); } catch (NumberFormatException ignored) {}
        try { return Double.parseDouble(val); } catch (NumberFormatException ignored) {}
        return val;
    }

    private static BigDecimal bd(Object v) {
        if (v == null) return BigDecimal.ZERO;
        try { return new BigDecimal(v.toString()); }
        catch (Exception e) { return BigDecimal.ZERO; }
    }

    private static long lng(Object v) {
        if (v == null) return 0;
        try { return Long.parseLong(v.toString().split("\\.")[0]); }
        catch (Exception e) { return 0; }
    }

    private static String str(Object v) {
        return v != null ? v.toString() : "";
    }
}
