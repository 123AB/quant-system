package router

import (
	"net/http"
	"time"

	"github.com/123AB/quant-gateway/internal/middleware"
	"github.com/123AB/quant-gateway/internal/proxy"
	"github.com/123AB/quant-gateway/internal/ws"
)

type Config struct {
	BizServiceURL string
	BizTimeout    time.Duration
	JWTSecret     string
	JWTSkipPaths  []string
	GlobalQPS     float64
	Hub           *ws.Hub
	WSPath        string
	Metrics       *middleware.Metrics
}

func NewRouter(cfg Config) (http.Handler, error) {
	rp, err := proxy.NewReverseProxy(cfg.BizServiceURL, cfg.BizTimeout)
	if err != nil {
		return nil, err
	}

	// Circuit breaker for upstream biz-service: open after 10 failures, recover after 3 successes, 30s open window
	breaker := middleware.NewCircuitBreaker(10, 3, 30*time.Second)

	mux := http.NewServeMux()

	// API routes → circuit breaker → reverse proxy to Java biz-service
	mux.Handle("/api/", middleware.CircuitBreakerHandler(breaker, rp.Handler()))

	// WebSocket endpoint
	mux.HandleFunc(cfg.WSPath, cfg.Hub.HandleUpgrade)

	// Health check
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok","breaker":"` + breaker.State() + `"}`))
	})

	// Prometheus-style metrics
	mux.HandleFunc("/metrics", middleware.PrometheusHandler(cfg.Metrics))

	// JSON metrics dashboard
	mux.HandleFunc("/metrics/json", cfg.Metrics.ServeHTTP)

	// Middleware chain (outermost runs first):
	// recovery → metrics → rate limit → JWT → mux
	var handler http.Handler = mux

	jwtMw := middleware.NewJWTMiddleware(cfg.JWTSecret, cfg.JWTSkipPaths)
	handler = jwtMw.Handler(handler)

	limiter := middleware.NewRateLimiter(cfg.GlobalQPS)
	handler = middleware.RateLimitHandler(limiter, handler)

	handler = middleware.MetricsHandler(cfg.Metrics, handler)

	handler = middleware.RecoveryHandler(handler)

	return handler, nil
}
