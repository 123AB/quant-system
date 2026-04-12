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
