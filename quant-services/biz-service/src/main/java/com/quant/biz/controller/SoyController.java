package com.quant.biz.controller;

import com.quant.common.domain.CrushMarginResult;
import com.quant.common.domain.FuturesQuote;
import com.quant.soy.entity.MarketQuoteEntity;
import com.quant.soy.service.SoyService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.*;

@RestController
@RequestMapping("/api/soy")
@RequiredArgsConstructor
public class SoyController {

    private final SoyService soyService;
    private final StringRedisTemplate redis;

    @GetMapping("/dashboard")
    public Map<String, Object> dashboard() {
        long t0 = System.currentTimeMillis();
        List<FuturesQuote> dceFutures = soyService.getDceFutures();
        CrushMarginResult crush = soyService.getCrushMargin(new BigDecimal("45.0"));
        long elapsed = System.currentTimeMillis() - t0;

        List<Map<String, Object>> dceList = new ArrayList<>();
        for (FuturesQuote fq : dceFutures) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("symbol", fq.getSymbol());
            m.put("name", fq.getName());
            m.put("exchange", fq.getExchange());
            m.put("unit", fq.getUnit());
            m.put("open", fq.getOpen());
            m.put("high", fq.getHigh());
            m.put("low", fq.getLow());
            m.put("close", fq.getClose());
            m.put("volume", fq.getVolume());
            m.put("change_pct", fq.getChangePct());
            dceList.add(m);
        }

        Map<String, Object> cbotMap = null;
        Map<Object, Object> cbotRaw = redis.opsForHash().entries("soy:cbot:latest");
        if (!cbotRaw.isEmpty()) {
            cbotMap = new LinkedHashMap<>();
            for (var e : cbotRaw.entrySet()) cbotMap.put(e.getKey().toString(), parseNum(e.getValue().toString()));
        }

        String usdcnyStr = redis.opsForValue().get("soy:fx:usdcny");
        Double usdcny = usdcnyStr != null ? Double.parseDouble(usdcnyStr) : null;

        Map<String, Object> crushMap = new LinkedHashMap<>();
        crushMap.put("cbot_usd_per_ton", crush.getCbotUsdPerTon());
        crushMap.put("freight_usd", crush.getFreightUsd());
        crushMap.put("cif_usd", crush.getCifUsd());
        crushMap.put("cif_cny", crush.getCifCny());
        crushMap.put("tariff_cny", crush.getTariffCny());
        crushMap.put("vat_cny", crush.getVatCny());
        crushMap.put("port_misc_cny", crush.getPortMiscCny());
        crushMap.put("landed_cost_cny", crush.getLandedCostCny());
        crushMap.put("processing_fee_cny", crush.getProcessingFeeCny());
        crushMap.put("total_bean_cost_cny", crush.getTotalBeanCostCny());
        crushMap.put("meal_price", crush.getMealPrice());
        crushMap.put("oil_price", crush.getOilPrice());
        crushMap.put("meal_revenue_cny", crush.getMealRevenueCny());
        crushMap.put("oil_revenue_cny", crush.getOilRevenueCny());
        crushMap.put("total_revenue_cny", crush.getTotalRevenueCny());
        crushMap.put("crush_margin_cny", crush.getCrushMarginCny());
        crushMap.put("is_profitable", crush.isProfitable());
        crushMap.put("signal", crush.getSignal() != null ? crush.getSignal().name() : null);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", "ok");
        result.put("elapsed_ms", elapsed);
        result.put("futures", Map.of("dce", dceList, "cbot", cbotMap != null ? cbotMap : Map.of()));
        result.put("fx", Map.of("usdcny", usdcny != null ? usdcny : 0,
                "validation", Map.of("status", "ok", "detail", "from redis cache")));
        result.put("crush", crushMap);
        result.put("dce_validations", Map.of());
        return result;
    }

    private static Object parseNum(String val) {
        if (val == null) return null;
        try { return Long.parseLong(val); } catch (NumberFormatException ignored) {}
        try { return Double.parseDouble(val); } catch (NumberFormatException ignored) {}
        return val;
    }

    @GetMapping("/futures")
    public List<FuturesQuote> futures() {
        return soyService.getDceFutures();
    }

    @GetMapping("/crush-margin")
    public CrushMarginResult crushMargin(
            @RequestParam(defaultValue = "45.0") BigDecimal freight) {
        return soyService.getCrushMargin(freight);
    }

    @GetMapping("/history/{symbol}")
    public List<MarketQuoteEntity> history(
            @PathVariable String symbol,
            @RequestParam(defaultValue = "30") int days) {
        return soyService.getHistory(symbol, days);
    }

    @GetMapping("/cot")
    public Map<String, Object> cot() {
        return soyService.getCot();
    }

    @GetMapping("/wasde")
    public Map<String, Object> wasde() {
        return soyService.getWasde();
    }

    @GetMapping("/china-imports")
    public Map<String, Object> chinaImports() {
        return soyService.getChinaImports();
    }

    @GetMapping("/inventory")
    public Map<String, Object> inventory() {
        return soyService.getInventory();
    }

    @GetMapping("/factor-signal")
    public Map<String, Object> factorSignal() {
        return soyService.getFactorSignal();
    }

    @PostMapping("/refresh")
    public Map<String, Object> refresh() {
        List<String> cleared = soyService.refreshCache();
        return Map.of("status", "ok", "cleared_keys", cleared);
    }
}
