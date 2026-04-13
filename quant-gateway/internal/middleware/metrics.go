package middleware

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

type Metrics struct {
	mu             sync.RWMutex
	requestCount   map[string]*atomic.Int64
	errorCount     map[string]*atomic.Int64
	latencySum     map[string]*atomic.Int64
	latencyBuckets map[string]*[7]atomic.Int64 // 10ms, 50ms, 100ms, 250ms, 500ms, 1s, 5s
	wsConnections  atomic.Int64
}

var bucketBounds = [7]time.Duration{
	10 * time.Millisecond,
	50 * time.Millisecond,
	100 * time.Millisecond,
	250 * time.Millisecond,
	500 * time.Millisecond,
	1 * time.Second,
	5 * time.Second,
}

func NewMetrics() *Metrics {
	return &Metrics{
		requestCount:   make(map[string]*atomic.Int64),
		errorCount:     make(map[string]*atomic.Int64),
		latencySum:     make(map[string]*atomic.Int64),
		latencyBuckets: make(map[string]*[7]atomic.Int64),
	}
}

func (m *Metrics) getOrCreate(path string) {
	m.mu.RLock()
	_, ok := m.requestCount[path]
	m.mu.RUnlock()
	if ok {
		return
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.requestCount[path]; !ok {
		m.requestCount[path] = &atomic.Int64{}
		m.errorCount[path] = &atomic.Int64{}
		m.latencySum[path] = &atomic.Int64{}
		m.latencyBuckets[path] = &[7]atomic.Int64{}
	}
}

func (m *Metrics) Record(path string, statusCode int, duration time.Duration) {
	m.getOrCreate(path)
	m.mu.RLock()
	defer m.mu.RUnlock()

	m.requestCount[path].Add(1)
	if statusCode >= 400 {
		m.errorCount[path].Add(1)
	}
	m.latencySum[path].Add(duration.Milliseconds())

	buckets := m.latencyBuckets[path]
	for i, bound := range bucketBounds {
		if duration <= bound {
			buckets[i].Add(1)
			break
		}
	}
}

func (m *Metrics) IncrWS()  { m.wsConnections.Add(1) }
func (m *Metrics) DecrWS()  { m.wsConnections.Add(-1) }
func (m *Metrics) WSCount() int64 { return m.wsConnections.Load() }

func (m *Metrics) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	type pathMetric struct {
		Path        string  `json:"path"`
		Requests    int64   `json:"requests"`
		Errors      int64   `json:"errors"`
		AvgLatencyMs float64 `json:"avg_latency_ms"`
	}

	var paths []pathMetric
	for path, count := range m.requestCount {
		total := count.Load()
		avgMs := float64(0)
		if total > 0 {
			avgMs = float64(m.latencySum[path].Load()) / float64(total)
		}
		paths = append(paths, pathMetric{
			Path:        path,
			Requests:    total,
			Errors:      m.errorCount[path].Load(),
			AvgLatencyMs: avgMs,
		})
	}

	sort.Slice(paths, func(i, j int) bool {
		return paths[i].Requests > paths[j].Requests
	})

	result := map[string]any{
		"websocket_connections": m.wsConnections.Load(),
		"paths":                paths,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func MetricsHandler(m *Metrics, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t0 := time.Now()
		sc := &statusCapture{ResponseWriter: w, statusCode: 200}
		next.ServeHTTP(sc, r)
		duration := time.Since(t0)

		path := normalizePath(r.URL.Path)
		m.Record(path, sc.statusCode, duration)
	})
}

func normalizePath(p string) string {
	if len(p) > 30 {
		return p[:30]
	}
	if p == "" {
		return "/"
	}
	return p
}

func PrometheusHandler(m *Metrics) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		m.mu.RLock()
		defer m.mu.RUnlock()

		w.Header().Set("Content-Type", "text/plain; version=0.0.4")

		fmt.Fprintf(w, "# HELP gateway_websocket_active_connections Current WebSocket connections\n")
		fmt.Fprintf(w, "# TYPE gateway_websocket_active_connections gauge\n")
		fmt.Fprintf(w, "gateway_websocket_active_connections %d\n\n", m.wsConnections.Load())

		fmt.Fprintf(w, "# HELP http_server_requests_total Total HTTP requests\n")
		fmt.Fprintf(w, "# TYPE http_server_requests_total counter\n")
		for path, count := range m.requestCount {
			fmt.Fprintf(w, "http_server_requests_total{path=%q} %d\n", path, count.Load())
		}

		fmt.Fprintf(w, "\n# HELP http_server_errors_total Total HTTP errors (4xx+5xx)\n")
		fmt.Fprintf(w, "# TYPE http_server_errors_total counter\n")
		for path, count := range m.errorCount {
			fmt.Fprintf(w, "http_server_errors_total{path=%q} %d\n", path, count.Load())
		}

		fmt.Fprintf(w, "\n# HELP http_server_duration_ms_sum Sum of request durations in ms\n")
		fmt.Fprintf(w, "# TYPE http_server_duration_ms_sum counter\n")
		for path, sum := range m.latencySum {
			fmt.Fprintf(w, "http_server_duration_ms_sum{path=%q} %d\n", path, sum.Load())
		}
	}
}
