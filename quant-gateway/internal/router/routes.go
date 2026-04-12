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
}

func NewRouter(cfg Config) (http.Handler, error) {
	rp, err := proxy.NewReverseProxy(cfg.BizServiceURL, cfg.BizTimeout)
	if err != nil {
		return nil, err
	}

	mux := http.NewServeMux()

	// API routes → reverse proxy to Java biz-service
	mux.Handle("/api/", rp.Handler())

	// WebSocket endpoint
	mux.HandleFunc(cfg.WSPath, cfg.Hub.HandleUpgrade)

	// Health check
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	// Apply middleware chain: recovery → rate limit → JWT
	var handler http.Handler = mux

	jwtMw := middleware.NewJWTMiddleware(cfg.JWTSecret, cfg.JWTSkipPaths)
	handler = jwtMw.Handler(handler)

	limiter := middleware.NewRateLimiter(cfg.GlobalQPS)
	handler = middleware.RateLimitHandler(limiter, handler)

	handler = middleware.RecoveryHandler(handler)

	return handler, nil
}
