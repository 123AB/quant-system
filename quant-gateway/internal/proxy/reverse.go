package proxy

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"
)

type ReverseProxy struct {
	target *url.URL
	proxy  *httputil.ReverseProxy
}

func NewReverseProxy(targetURL string, timeout time.Duration) (*ReverseProxy, error) {
	target, err := url.Parse(targetURL)
	if err != nil {
		return nil, err
	}

	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.Transport = &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 50,
		IdleConnTimeout:     90 * time.Second,
		ResponseHeaderTimeout: timeout,
	}

	return &ReverseProxy{target: target, proxy: proxy}, nil
}

func (rp *ReverseProxy) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.URL.Host = rp.target.Host
		r.URL.Scheme = rp.target.Scheme
		r.Host = rp.target.Host

		// Strip /api prefix if upstream expects it without
		if strings.HasPrefix(r.URL.Path, "/api/") {
			r.URL.Path = "/api/" + strings.TrimPrefix(r.URL.Path, "/api/")
		}

		rp.proxy.ServeHTTP(w, r)
	})
}
