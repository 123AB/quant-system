# Quant System

量化交易系统 — Go Gateway + Java Business + Python Agent + TimescaleDB + Redis

## Architecture

```
Client (Expo/RN)
    │
    ▼
┌─────────────────────┐
│  Go Gateway (Kratos)│   REST / WebSocket
│  - JWT auth         │
│  - Rate limit       │
│  - Circuit breaker  │
└─────────┬───────────┘
          │ gRPC
    ┌─────┴─────┐
    ▼           ▼
┌──────────┐  ┌───────────────┐
│  Java    │  │  Python Agent │
│  Biz Svc │  │  - pipeline   │
│  (Spring)│  │  - signal     │
└────┬─────┘  └───────┬───────┘
     │                │
     ├────────────────┤
     ▼                ▼
┌──────────┐   ┌──────────┐
│PostgreSQL│   │  Redis   │
│+Timescale│   │  cache   │
└──────────┘   └──────────┘
```

## Tech Stack

| Layer    | Language | Framework          | Purpose                                    |
|----------|----------|--------------------|--------------------------------------------|
| Gateway  | Go 1.22  | Kratos             | REST→gRPC 转换, JWT, 限流, 熔断, WebSocket |
| Business | Java 21  | Spring Boot 3.4    | 压榨利润计算, 因子信号, LOF 溢价, 用户管理  |
| Agent    | Python 3.12 | LangGraph + APScheduler | 数据管道 FSM, LLM 信号合成, MCP Server |
| Database | -        | PostgreSQL 16 + TimescaleDB | 时序数据, 关系数据, JSONB 文档       |
| Cache    | -        | Redis 7            | 行情缓存, Pub/Sub, Streams 异步消息         |
| Frontend | TypeScript | Expo / React Native | 移动端 dashboard                        |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/123AB/quant-system.git
cd quant-system

# 2. Environment
cp .env.example .env
# Edit .env with your secrets

# 3. Start infrastructure
cd docker
docker compose up -d postgres redis

# 4. Verify
docker compose exec postgres psql -U quant -c "SELECT * FROM timescaledb_information.hypertables;"
docker compose exec redis redis-cli ping
```

## Project Structure

```
quant-system/
├── docker/
│   ├── docker-compose.yml       # Production compose
│   ├── docker-compose.dev.yml   # Dev overrides (pgAdmin, RedisInsight)
│   ├── init.sql                 # DDL (TimescaleDB hypertables + tables)
│   ├── gateway/Dockerfile
│   ├── biz-service/Dockerfile
│   ├── data-pipeline/Dockerfile
│   ├── signal-agent/Dockerfile
│   └── frontend/nginx.conf
├── quant-proto/                 # Protobuf definitions
│   ├── buf.yaml
│   ├── buf.gen.yaml
│   ├── common/                  # Shared types (MarketContext, enums)
│   ├── fund/                    # Fund service
│   ├── soy/                     # Soy service
│   ├── user/                    # User service
│   ├── alert/                   # Alert service
│   └── agent/                   # Signal agent service
├── .env.example
├── .gitignore
└── README.md
```

## Design Docs

See [quant-system-design/](../quant-system-design/) for the full architecture plan.

## Containers (Phase 1)

| Container      | Image                    | Port   | Resources        |
|----------------|--------------------------|--------|------------------|
| postgres       | timescale/timescaledb:pg16 | 5432 | 1 CPU, 1G RAM   |
| redis          | redis:7-alpine           | 6379   | 0.25 CPU, 256M   |
| biz-service    | custom (Java 21)         | 9001   | 1 CPU, 512M      |
| data-pipeline  | custom (Python 3.12)     | -      | 0.5 CPU, 256M    |
| signal-agent   | custom (Python 3.12)     | 50052  | 0.5 CPU, 512M    |
| gateway        | custom (Go 1.22)         | 8080   | 0.5 CPU, 256M    |
| frontend       | nginx:1.27-alpine        | 80     | 0.25 CPU, 128M   |

## License

MIT
