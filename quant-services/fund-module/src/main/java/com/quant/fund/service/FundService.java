package com.quant.fund.service;

import com.quant.fund.entity.FundConfigEntity;
import com.quant.fund.entity.LofPremiumEntity;
import com.quant.fund.repository.FundConfigRepository;
import com.quant.fund.repository.LofPremiumRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class FundService {

    private final FundConfigRepository configRepo;
    private final LofPremiumRepository premiumRepo;
    private final StringRedisTemplate redis;

    public List<FundConfigEntity> listFunds(boolean activeOnly) {
        return activeOnly ? configRepo.findByActiveTrue() : configRepo.findAll();
    }

    public Optional<FundConfigEntity> getFundDetail(String code) {
        return configRepo.findByCode(code);
    }

    /**
     * Read LOF premium from Redis (written by Python data-pipeline or fund-tracker).
     */
    public List<Map<String, Object>> getLofPremiums(List<String> codes) {
        if (codes == null || codes.isEmpty()) {
            List<FundConfigEntity> active = configRepo.findByActiveTrue();
            codes = active.stream().map(FundConfigEntity::getCode).toList();
        }

        List<Map<String, Object>> premiums = new ArrayList<>();
        for (String code : codes) {
            Map<Object, Object> cached = redis.opsForHash().entries("fund:premium:" + code);
            if (!cached.isEmpty()) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("fund_code", code);
                item.putAll(cached.entrySet().stream()
                        .collect(LinkedHashMap::new,
                                (m, e) -> m.put(e.getKey().toString(), e.getValue()),
                                Map::putAll));
                premiums.add(item);
            }
        }
        return premiums;
    }

    public List<LofPremiumEntity> getPremiumHistory(String fundCode, int days) {
        Instant since = Instant.now().minus(days, ChronoUnit.DAYS);
        return premiumRepo.findByFundCodeAndTimeAfterOrderByTimeDesc(fundCode, since);
    }
}
