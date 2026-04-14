package com.quant.biz.controller;

import com.quant.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserService userService;

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody Map<String, String> body) {
        String username = body.get("username");
        String password = body.get("password");
        String email = body.getOrDefault("email", username + "@quant.local");
        if (username == null || username.isBlank()) {
            throw new IllegalArgumentException("username is required");
        }
        if (password == null || password.length() < 6) {
            throw new IllegalArgumentException("password must be at least 6 characters");
        }
        return userService.register(username, password, email);
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body) {
        return userService.login(body.get("username"), body.get("password"));
    }

    @PostMapping("/refresh")
    public Map<String, Object> refresh(@RequestBody Map<String, String> body) {
        return userService.refreshToken(body.get("refresh_token"));
    }
}
