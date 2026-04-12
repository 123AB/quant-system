package com.quant.soy.repository;

import com.quant.soy.entity.CrushMarginEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.List;

public interface CrushMarginRepository extends JpaRepository<CrushMarginEntity, Long> {

    List<CrushMarginEntity> findByTimeAfterOrderByTimeDesc(Instant since);
}
