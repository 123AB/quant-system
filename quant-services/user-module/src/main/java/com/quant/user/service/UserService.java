package com.quant.user.service;

import com.quant.common.exception.BusinessException;
import com.quant.user.entity.UserEntity;
import com.quant.user.repository.UserRepository;
import com.quant.user.security.JwtProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepo;
    private final JwtProvider jwtProvider;
    private final PasswordEncoder passwordEncoder;

    public Map<String, Object> register(String username, String password, String email) {
        if (userRepo.existsByUsername(username)) {
            throw new BusinessException("USER_EXISTS", "用户名已存在");
        }
        if (userRepo.existsByEmail(email)) {
            throw new BusinessException("EMAIL_EXISTS", "邮箱已注册");
        }

        var user = new UserEntity();
        user.setUsername(username);
        user.setEmail(email);
        user.setPasswordHash(passwordEncoder.encode(password));
        userRepo.save(user);

        return buildAuthResponse(user);
    }

    public Map<String, Object> login(String username, String password) {
        var user = userRepo.findByUsername(username)
                .orElseThrow(() -> new BusinessException("NOT_FOUND", "用户不存在"));

        if (!passwordEncoder.matches(password, user.getPasswordHash())) {
            throw new BusinessException("BAD_CREDENTIALS", "密码错误");
        }

        return buildAuthResponse(user);
    }

    public Map<String, Object> refreshToken(String refreshToken) {
        if (!jwtProvider.validateToken(refreshToken)) {
            throw new BusinessException("INVALID_TOKEN", "Refresh token 无效");
        }

        var claims = jwtProvider.parseToken(refreshToken);
        long userId = Long.parseLong(claims.getSubject());
        var user = userRepo.findById(userId)
                .orElseThrow(() -> new BusinessException("NOT_FOUND", "用户不存在"));

        return buildAuthResponse(user);
    }

    public UserEntity getProfile(long userId) {
        return userRepo.findById(userId)
                .orElseThrow(() -> new BusinessException("NOT_FOUND", "用户不存在"));
    }

    private Map<String, Object> buildAuthResponse(UserEntity user) {
        String accessToken = jwtProvider.generateAccessToken(user.getId(), user.getUsername());
        String refreshTokenStr = jwtProvider.generateRefreshToken(user.getId(), user.getUsername());

        return Map.of(
                "access_token", accessToken,
                "refresh_token", refreshTokenStr,
                "expires_in", 3600,
                "user", Map.of(
                        "id", user.getId(),
                        "username", user.getUsername(),
                        "email", user.getEmail()
                )
        );
    }
}
