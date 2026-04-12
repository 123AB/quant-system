package com.quant.biz.controller;

import com.quant.fund.entity.FundConfigEntity;
import com.quant.fund.service.FundService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/fund")
@RequiredArgsConstructor
public class FundController {

    private final FundService fundService;

    @GetMapping("/list")
    public List<FundConfigEntity> list(@RequestParam(defaultValue = "true") boolean activeOnly) {
        return fundService.listFunds(activeOnly);
    }

    @GetMapping("/{code}")
    public FundConfigEntity detail(@PathVariable String code) {
        return fundService.getFundDetail(code).orElseThrow();
    }

    @GetMapping("/premium")
    public List<Map<String, Object>> premiums(@RequestParam(required = false) List<String> codes) {
        return fundService.getLofPremiums(codes);
    }
}
