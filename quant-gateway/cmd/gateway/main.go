package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"
	"gopkg.in/yaml.v3"

	"github.com/123AB/quant-gateway/internal/router"
	"github.com/123AB/quant-gateway/internal/ws"
)

type AppConfig struct {
	Server struct {
		Addr         string `yaml:"addr"`
		ReadTimeout  string `yaml:"read_timeout"`
		WriteTimeout string `yaml:"write_timeout"`
	} `yaml:"server"`

	Upstream struct {
		BizService string `yaml:"biz_service"`
		Timeout    string `yaml:"timeout"`
	} `yaml:"upstream"`

	JWT struct {
		Secret    string   `yaml:"secret"`
		SkipPaths []string `yaml:"skip_paths"`
	} `yaml:"jwt"`

	RateLimit struct {
		GlobalQPS float64 `yaml:"global_qps"`
	} `yaml:"rate_limit"`

	Redis struct {
		Addr     string `yaml:"addr"`
		Password string `yaml:"password"`
		DB       int    `yaml:"db"`
	} `yaml:"redis"`

	WebSocket struct {
		Path         string `yaml:"path"`
		RedisChannel string `yaml:"redis_channel"`
	} `yaml:"websocket"`
}

func main() {
	cfgPath := "configs/config.yaml"
	if p := os.Getenv("CONFIG_PATH"); p != "" {
		cfgPath = p
	}

	data, err := os.ReadFile(cfgPath)
	if err != nil {
		log.Fatalf("Failed to read config: %v", err)
	}

	var cfg AppConfig
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		log.Fatalf("Failed to parse config: %v", err)
	}

	// Override from environment
	if addr := os.Getenv("LISTEN_ADDR"); addr != "" {
		cfg.Server.Addr = addr
	}
	if bizURL := os.Getenv("BIZ_SERVICE_URL"); bizURL != "" {
		cfg.Upstream.BizService = bizURL
	}
	if redisAddr := os.Getenv("REDIS_ADDR"); redisAddr != "" {
		cfg.Redis.Addr = redisAddr
	}
	if secret := os.Getenv("JWT_SECRET"); secret != "" {
		cfg.JWT.Secret = secret
	}

	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr,
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer rdb.Close()

	hub := ws.NewHub(rdb, cfg.WebSocket.RedisChannel)

	bizTimeout, _ := time.ParseDuration(cfg.Upstream.Timeout)
	if bizTimeout == 0 {
		bizTimeout = 5 * time.Second
	}

	globalQPS := cfg.RateLimit.GlobalQPS
	if globalQPS <= 0 {
		globalQPS = 5000
	}

	handler, err := router.NewRouter(router.Config{
		BizServiceURL: cfg.Upstream.BizService,
		BizTimeout:    bizTimeout,
		JWTSecret:     cfg.JWT.Secret,
		JWTSkipPaths:  cfg.JWT.SkipPaths,
		GlobalQPS:     globalQPS,
		Hub:           hub,
		WSPath:        cfg.WebSocket.Path,
	})
	if err != nil {
		log.Fatalf("Failed to create router: %v", err)
	}

	readTimeout, _ := time.ParseDuration(cfg.Server.ReadTimeout)
	writeTimeout, _ := time.ParseDuration(cfg.Server.WriteTimeout)

	srv := &http.Server{
		Addr:         cfg.Server.Addr,
		Handler:      handler,
		ReadTimeout:  readTimeout,
		WriteTimeout: writeTimeout,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go hub.Run(ctx)

	go func() {
		log.Printf("Gateway listening on %s", cfg.Server.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-ctx.Done()
	log.Println("Shutting down gateway...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Shutdown error: %v", err)
	}

	log.Println("Gateway stopped")
}

