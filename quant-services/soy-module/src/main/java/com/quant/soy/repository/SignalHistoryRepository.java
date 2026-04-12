package com.quant.soy.repository;

import com.quant.soy.entity.SignalHistoryEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

public interface SignalHistoryRepository extends JpaRepository<SignalHistoryEntity, Long> {

    Optional<SignalHistoryEntity> findFirstByOrderByTimeDesc();

    List<SignalHistoryEntity> findByTimeAfterOrderByTimeDesc(Instant since);
}
