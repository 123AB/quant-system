package com.quant.soy.engine;

import com.quant.common.domain.FactorSignalResult;
import com.quant.common.domain.FactorSignalResult.FactorDetail;
import com.quant.common.enums.SignalLevel;

import java.util.ArrayList;
import java.util.List;

/**
 * 8-factor rule-based signal engine — mirrors Python factor_signal/engine.py.
 *
 * Factors: crush_margin, basis, cbot_trend, usdcny_trend, cot_net,
 *          seasonal, technical_ma, volume_price
 */
public final class RuleBasedSignalEngine {

    private RuleBasedSignalEngine() {}

    public static FactorSignalResult score(
            double crushMargin,
            double basisValue,
            double cbotChangePct,
            double usdcnyChangePct,
            double cotNetChange,
            int currentMonth,
            double priceVsMa20Pct,
            double volumeChangePct
    ) {
        List<FactorDetail> factors = new ArrayList<>();
        int totalScore = 0;

        // Factor 1: Crush margin
        int crushPts = crushMargin < 0 ? 2 : (crushMargin < 100 ? 1 : (crushMargin > 300 ? -1 : 0));
        factors.add(FactorDetail.builder()
                .name("crush_margin").label("压榨利润")
                .value(crushMargin).points(crushPts)
                .signal(crushPts > 0 ? "bullish" : (crushPts < 0 ? "bearish" : "neutral"))
                .description(crushMargin < 0 ? "亏损压缩压榨，利多豆粕" : "利润尚可")
                .build());
        totalScore += crushPts;

        // Factor 2: Basis
        int basisPts = basisValue > 100 ? 2 : (basisValue > 0 ? 1 : (basisValue < -100 ? -1 : 0));
        factors.add(FactorDetail.builder()
                .name("basis").label("基差")
                .value(basisValue).points(basisPts)
                .signal(basisPts > 0 ? "bullish" : (basisPts < 0 ? "bearish" : "neutral"))
                .description(basisValue > 0 ? "现货升水，近月偏强" : "期货升水")
                .build());
        totalScore += basisPts;

        // Factor 3: CBOT trend
        int cbotPts = cbotChangePct > 1.0 ? 1 : (cbotChangePct < -1.0 ? -1 : 0);
        factors.add(FactorDetail.builder()
                .name("cbot_trend").label("美豆趋势")
                .value(cbotChangePct).points(cbotPts)
                .signal(cbotPts > 0 ? "bullish" : (cbotPts < 0 ? "bearish" : "neutral"))
                .description(cbotChangePct > 0 ? "美豆上涨带动成本" : "美豆走弱")
                .build());
        totalScore += cbotPts;

        // Factor 4: USD/CNY trend
        int fxPts = usdcnyChangePct > 0.3 ? 1 : (usdcnyChangePct < -0.3 ? -1 : 0);
        factors.add(FactorDetail.builder()
                .name("usdcny_trend").label("汇率趋势")
                .value(usdcnyChangePct).points(fxPts)
                .signal(fxPts > 0 ? "bullish" : (fxPts < 0 ? "bearish" : "neutral"))
                .description(usdcnyChangePct > 0 ? "人民币贬值推高进口成本" : "人民币升值")
                .build());
        totalScore += fxPts;

        // Factor 5: COT positioning
        int cotPts = cotNetChange > 15000 ? 1 : (cotNetChange < -15000 ? -1 : 0);
        factors.add(FactorDetail.builder()
                .name("cot_net").label("CFTC持仓")
                .value(cotNetChange).points(cotPts)
                .signal(cotPts > 0 ? "bullish" : (cotPts < 0 ? "bearish" : "neutral"))
                .description(cotNetChange > 0 ? "投机多头增仓" : "投机空头增仓")
                .build());
        totalScore += cotPts;

        // Factor 6: Seasonal
        int seasonPts = (currentMonth >= 5 && currentMonth <= 9) ? 1 : (currentMonth == 10 ? -1 : 0);
        factors.add(FactorDetail.builder()
                .name("seasonal").label("季节性")
                .value(currentMonth).points(seasonPts)
                .signal(seasonPts > 0 ? "bullish" : (seasonPts < 0 ? "bearish" : "neutral"))
                .description(seasonPts > 0 ? "天气市季节偏多" : "非天气市季节")
                .build());
        totalScore += seasonPts;

        // Factor 7: Technical MA20
        int maPts = priceVsMa20Pct > 2 ? 1 : (priceVsMa20Pct < -2 ? -1 : 0);
        factors.add(FactorDetail.builder()
                .name("technical_ma").label("MA20偏离")
                .value(priceVsMa20Pct).points(maPts)
                .signal(maPts > 0 ? "bullish" : (maPts < 0 ? "bearish" : "neutral"))
                .description(priceVsMa20Pct > 0 ? "价格高于MA20" : "价格低于MA20")
                .build());
        totalScore += maPts;

        // Factor 8: Volume-price
        int volPts = volumeChangePct > 30 ? 1 : (volumeChangePct < -30 ? -1 : 0);
        factors.add(FactorDetail.builder()
                .name("volume_price").label("量价配合")
                .value(volumeChangePct).points(volPts)
                .signal(volPts > 0 ? "bullish" : (volPts < 0 ? "bearish" : "neutral"))
                .description(volumeChangePct > 0 ? "放量上涨" : "缩量")
                .build());
        totalScore += volPts;

        String compositeSignal;
        SignalLevel level;
        if (totalScore >= 5) {
            compositeSignal = "强烈做多"; level = SignalLevel.STRONG_BULLISH;
        } else if (totalScore >= 3) {
            compositeSignal = "做多"; level = SignalLevel.BULLISH;
        } else if (totalScore >= 1) {
            compositeSignal = "观望偏多"; level = SignalLevel.NEUTRAL_BULLISH;
        } else if (totalScore >= -2) {
            compositeSignal = "观望"; level = SignalLevel.NEUTRAL;
        } else {
            compositeSignal = "偏空"; level = SignalLevel.BEARISH;
        }

        return FactorSignalResult.builder()
                .compositeScore(totalScore)
                .compositeSignal(compositeSignal)
                .signalLevel(level)
                .factors(factors)
                .keyPriceLevels(List.of())
                .analystRules(List.of(
                    "价格触及支撑位+成交量突增→底部确认",
                    "自底部累涨1000-1200元/吨→分批减仓",
                    "美豆大跌但国内不跟→国内内生强势",
                    "6-9月09合约季节性偏多"
                ))
                .build();
    }
}
