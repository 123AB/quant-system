package com.quant.biz.config;

import com.quant.common.exception.BusinessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<Map<String, Object>> handleBusiness(BusinessException ex) {
        HttpStatus status = switch (ex.getCode()) {
            case "NOT_FOUND" -> HttpStatus.NOT_FOUND;
            case "BAD_CREDENTIALS", "INVALID_TOKEN" -> HttpStatus.UNAUTHORIZED;
            default -> HttpStatus.BAD_REQUEST;
        };
        return ResponseEntity.status(status).body(Map.of(
                "error", ex.getCode(),
                "message", ex.getMessage()
        ));
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<Map<String, Object>> handleDataIntegrity(DataIntegrityViolationException ex) {
        String msg = ex.getMostSpecificCause().getMessage();
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of(
                "error", "VALIDATION_ERROR",
                "message", msg != null ? msg : "Data integrity violation"
        ));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArg(IllegalArgumentException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of(
                "error", "INVALID_ARGUMENT",
                "message", ex.getMessage() != null ? ex.getMessage() : "Invalid argument"
        ));
    }
}
