FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /gateway ./cmd/gateway/main.go

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
COPY --from=builder /gateway /usr/local/bin/gateway
COPY configs/ /etc/gateway/
EXPOSE 8080 8443
ENTRYPOINT ["gateway"]
CMD ["-conf", "/etc/gateway/config.yaml"]
