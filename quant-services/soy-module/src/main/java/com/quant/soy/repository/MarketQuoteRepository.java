package com.quant.soy.repository;

import com.quant.soy.entity.MarketQuoteEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;

public interface MarketQuoteRepository extends JpaRepository<MarketQuoteEntity, Long> {

    @Query(value = """
            SELECT * FROM market_quotes
            WHERE symbol = :symbol AND time > :since
            ORDER BY time DESC
            LIMIT :limit
            """, nativeQuery = true)
    List<MarketQuoteEntity> findRecentBySymbol(
            @Param("symbol") String symbol,
            @Param("since") Instant since,
            @Param("limit") int limit);

    @Query(value = """
            SELECT time_bucket('30 minutes', time) AS time,
                   symbol, source,
                   first(\"open\", time) AS \"open\",
                   max(high) AS high,
                   min(low) AS low,
                   last(\"close\", time) AS \"close\",
                   sum(volume) AS volume,
                   sum(amount) AS amount,
                   last(change_pct, time) AS change_pct,
                   'aggregated' AS data_quality
            FROM market_quotes
            WHERE symbol = :symbol AND time BETWEEN :from AND :to
            GROUP BY time_bucket('30 minutes', time), symbol, source
            ORDER BY time
            """, nativeQuery = true)
    List<MarketQuoteEntity> aggregateHalfHourly(
            @Param("symbol") String symbol,
            @Param("from") Instant from,
            @Param("to") Instant to);
}
