FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git
WORKDIR /build
COPY . .
RUN go mod tidy && go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /gateway ./cmd/gateway/main.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata curl
WORKDIR /app
COPY --from=builder /gateway /app/gateway
COPY configs/ /app/configs/
EXPOSE 8080
ENV TZ=Asia/Shanghai
ENTRYPOINT ["/app/gateway"]
