package com.quant.common.domain;

import com.quant.common.enums.SignalLevel;
import lombok.Builder;
import lombok.Data;

import java.util.List;

@Data
@Builder
public class FactorSignalResult {
    private String date;
    private int compositeScore;
    private String compositeSignal;
    private SignalLevel signalLevel;
    private List<FactorDetail> factors;
    private List<Integer> keyPriceLevels;
    private List<String> analystRules;

    @Data
    @Builder
    public static class FactorDetail {
        private String name;
        private String label;
        private double value;
        private String signal;
        private String description;
        private int points;
    }
}
