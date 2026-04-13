package com.quant.soy.engine;

import com.quant.common.domain.FactorSignalResult;
import com.quant.common.enums.SignalLevel;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class RuleBasedSignalEngineTest {

    @Test
    void strongBullishScenario() {
        FactorSignalResult r = RuleBasedSignalEngine.score(
                -50,    // loss → +2
                150,    // high basis → +2
                2.0,    // CBOT up → +1
                0.5,    // CNY weaken → +1
                20000,  // COT bullish → +1
                7,      // Jul weather → +1
                3.0,    // above MA20 → +1
                50      // volume up → +1
        );

        assertEquals(8, r.getFactors().size());
        assertTrue(r.getCompositeScore() >= 5);
        assertEquals(SignalLevel.STRONG_BULLISH, r.getSignalLevel());
        assertEquals("强烈做多", r.getCompositeSignal());
    }

    @Test
    void bearishScenario() {
        FactorSignalResult r = RuleBasedSignalEngine.score(
                400,    // rich crush → -1
                -150,   // negative basis → -1
                -2.0,   // CBOT down → -1
                -0.5,   // CNY strengthen → -1
                -20000, // COT bearish → -1
                10,     // Oct sell → -1
                -3.0,   // below MA20 → -1
                -50     // volume drop → -1
        );

        assertTrue(r.getCompositeScore() <= -2);
        assertEquals(SignalLevel.BEARISH, r.getSignalLevel());
        assertEquals("偏空", r.getCompositeSignal());
    }

    @Test
    void neutralScenario() {
        FactorSignalResult r = RuleBasedSignalEngine.score(
                150,    // normal → 0
                0,      // flat basis → 0
                0.5,    // CBOT flat → 0
                0.1,    // FX flat → 0
                5000,   // COT normal → 0
                1,      // Jan → 0
                0.5,    // near MA20 → 0
                10      // normal vol → 0
        );

        assertEquals(0, r.getCompositeScore());
        assertEquals(SignalLevel.NEUTRAL, r.getSignalLevel());
    }

    @Test
    void allFactorsPresent() {
        FactorSignalResult r = RuleBasedSignalEngine.score(0, 0, 0, 0, 0, 1, 0, 0);

        assertEquals(8, r.getFactors().size());
        assertFalse(r.getAnalystRules().isEmpty());

        var factorNames = r.getFactors().stream().map(FactorSignalResult.FactorDetail::getName).toList();
        assertTrue(factorNames.contains("crush_margin"));
        assertTrue(factorNames.contains("basis"));
        assertTrue(factorNames.contains("cbot_trend"));
        assertTrue(factorNames.contains("usdcny_trend"));
        assertTrue(factorNames.contains("cot_net"));
        assertTrue(factorNames.contains("seasonal"));
        assertTrue(factorNames.contains("technical_ma"));
        assertTrue(factorNames.contains("volume_price"));
    }
}
