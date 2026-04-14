package com.quant.fund.service;

import com.quant.fund.entity.FundConfigEntity;
import com.quant.fund.entity.LofPremiumEntity;
import com.quant.fund.repository.FundConfigRepository;
import com.quant.fund.repository.LofPremiumRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

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

    /**
     * Return live fund data by reading from Redis (written by Python fund-pipeline).
     * Falls back to config-only data if Redis has no entry for a fund.
     */
    public List<Map<String, Object>> listFundsLive(boolean activeOnly) {
        List<FundConfigEntity> configs = activeOnly
                ? configRepo.findByActiveTrue()
                : configRepo.findAll();

        List<Map<String, Object>> result = new ArrayList<>();
        for (FundConfigEntity fc : configs) {
            Map<Object, Object> raw = redis.opsForHash().entries("fund:data:" + fc.getCode());
            if (!raw.isEmpty()) {
                Map<String, Object> item = new LinkedHashMap<>();
                for (var entry : raw.entrySet()) {
                    String key = entry.getKey().toString();
                    String val = entry.getValue().toString();
                    item.put(key, parseNumericField(key, val));
                }
                result.add(item);
            } else {
                result.add(Map.of(
                        "code", fc.getCode(),
                        "name", fc.getName(),
                        "exchange", fc.getExchange() != null ? fc.getExchange() : "",
                        "index_sina", fc.getIndexSina() != null ? fc.getIndexSina() : "",
                        "index_name", fc.getIndexName() != null ? fc.getIndexName() : "",
                        "price", (Object) null,
                        "premium_pct", (Object) null,
                        "updated_at", ""
                ));
            }
        }
        return result;
    }

    public List<FundConfigEntity> listFunds(boolean activeOnly) {
        return activeOnly ? configRepo.findByActiveTrue() : configRepo.findAll();
    }

    public Optional<FundConfigEntity> getFundDetail(String code) {
        return configRepo.findByCode(code);
    }

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

    private static final Set<String> NUMERIC_FIELDS = Set.of(
            "price", "prev_close", "change_pct", "volume_wan",
            "open", "high", "low", "index_change_pct", "premium_pct"
    );

    private Object parseNumericField(String key, String val) {
        if (val == null || val.isEmpty()) return null;
        if (!NUMERIC_FIELDS.contains(key)) return val;
        try {
            return Double.parseDouble(val);
        } catch (NumberFormatException e) {
            return val;
        }
    }
}
