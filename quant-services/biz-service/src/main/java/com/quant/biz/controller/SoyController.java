package com.quant.biz.controller;

import com.quant.common.domain.CrushMarginResult;
import com.quant.common.domain.FuturesQuote;
import com.quant.soy.entity.MarketQuoteEntity;
import com.quant.soy.service.SoyService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.*;

@RestController
@RequestMapping("/api/soy")
@RequiredArgsConstructor
public class SoyController {

    private final SoyService soyService;

    @GetMapping("/dashboard")
    public Map<String, Object> dashboard() {
        long t0 = System.currentTimeMillis();
        List<FuturesQuote> futures = soyService.getDceFutures();
        CrushMarginResult crush = soyService.getCrushMargin(new BigDecimal("45.0"));
        long elapsed = System.currentTimeMillis() - t0;

        return Map.of(
                "status", "ok",
                "elapsed_ms", elapsed,
                "futures", futures,
                "crush", crush
        );
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
