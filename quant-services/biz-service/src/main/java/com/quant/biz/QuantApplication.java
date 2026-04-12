package com.quant.biz;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication(scanBasePackages = "com.quant")
@EntityScan(basePackages = "com.quant")
@EnableJpaRepositories(basePackages = "com.quant")
@EnableScheduling
public class QuantApplication {

    public static void main(String[] args) {
        SpringApplication.run(QuantApplication.class, args);
    }
}
