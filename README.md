# Quant System — 量化交易微服务系统

LOF 基金套利 + 大豆期货研究的量化交易平台，采用 Go/Java/Python 多语言微服务架构。

## Architecture

```
┌─────────────┐     ┌─────────────────────────────────────────┐
│   Frontend   │────▶│  Go Gateway (quant-gateway :8080)       │
│   (Nginx)    │     │  JWT · Rate Limit · WebSocket Hub       │
└─────────────┘     └──────────┬───────────────────────────────┘
                               │ HTTP reverse proxy
                    ┌──────────▼───────────────────────────────┐
                    │  Java biz-service (Spring Boot :8081)     │
                    │  REST API · Fund · Soy · Auth · Alert    │
                    └──────────┬───────────────────────────────┘
                               │ JPA / Redis
              ┌────────────────┼────────────────┐
    ┌─────────▼──────┐  ┌──────▼──────┐  ┌──────▼──────────────┐
    │  PostgreSQL +   │  │   Redis 7   │  │  Python Agents      │
    │  TimescaleDB    │  │  Cache/Pub  │  │  data-pipeline FSM  │
    │  :5432          │  │  :6379      │  │  signal-agent LLM   │
    └────────────────┘  └─────────────┘  │  MCP Server          │
                                         └──────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Gateway | Go 1.22, gorilla/websocket, go-redis |
| Business | Java 21, Spring Boot 3.4, Virtual Threads, JPA |
| Data Pipeline | Python 3.12, APScheduler, FSM (4-phase) |
| Signal Agent | Python 3.12, LangGraph, OpenAI/Anthropic/Qwen |
| MCP Server | Python, FastMCP (6 tools, 2 resources) |
| Database | PostgreSQL 16 + TimescaleDB (hypertables) |
| Cache/Messaging | Redis 7 (cache, Pub/Sub, Streams) |
| Proto | Protobuf 3, buf CLI |

## Project Structure

```
quant-system/
├── quant-gateway/          # Go API Gateway
│   ├── cmd/gateway/        # Entry point
│   ├── internal/           # Middleware, router, WebSocket, proxy
│   └── configs/            # YAML config
├── quant-services/         # Java Spring Boot (Gradle multi-module)
│   ├── quant-common/       # Domain objects, enums
│   ├── soy-module/         # Crush margin, factor signal, entities
│   ├── fund-module/        # LOF premium, fund config
│   ├── user-module/        # JWT auth, user CRUD
│   ├── alert-module/       # Redis stream consumer, alert rules
│   └── biz-service/        # Spring Boot main app + REST controllers
├── quant-agent/            # Python agent layer
│   └── src/
│       ├── data_pipeline/  # FSM: health → fetch → validate → publish
│       ├── signal_agent/   # LangGraph: gather → compress → reason → emit
│       ├── mcp_server/     # FastMCP for Cursor IDE
│       ├── fetchers/       # DCE, CBOT, FX, USDA, COT data sources
│       ├── crusher/        # Crush margin calculator
│       ├── validators/     # Cross-source validation
│       └── factor_signal/  # 8-factor scoring engine
├── quant-proto/            # Protobuf definitions (shared)
│   ├── common/             # MarketContext, enums
│   ├── fund/               # FundService
│   ├── soy/                # SoyService
│   ├── user/               # UserService
│   ├── alert/              # AlertService
│   └── agent/              # SignalService
└── docker/                 # Docker Compose + Dockerfiles + init.sql
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/123AB/quant-system.git
cd quant-system

# 2. Copy env
cp .env.example .env
# Edit .env: set LLM_PROVIDER, API keys, etc.

# 3. Start infrastructure
cd docker
docker compose up -d postgres redis

# 4. Verify
docker compose exec postgres psql -U quant -d quant -c "\\dt"
docker compose exec redis redis-cli ping

# 5. Start all services (when Docker images are built)
docker compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Gateway | 8080 | REST API entry + WebSocket |
| biz-service | 8081 | Java business logic |
| data-pipeline | — | Scheduled data fetching (30s/30min) |
| signal-agent | — | LLM signal synthesis (30min) |
| PostgreSQL | 5432 | TimescaleDB (hypertables, continuous aggregates) |
| Redis | 6379 | Cache, Pub/Sub, Streams |
| Frontend | 80 | Nginx static + proxy |

## MCP Server (Cursor IDE)

The MCP server exposes 6 tools for use in Cursor:
- `get_dce_futures` — DCE commodity futures
- `get_crush_margin` — Soybean crush margin calculation
- `get_usda_supply_demand` — USDA world/China balance sheet
- `get_cot_positioning` — CFTC COT positioning
- `get_factor_signal` — 8-factor quantitative scoring
- `validate_data_quality` — Cross-source data validation

Configure in `~/.cursor/mcp.json` (see `.cursor/mcp.json` for reference).

## Data Flow

```
akshare/Sina → data-pipeline (FSM) → PG hypertable + Redis cache
                                          ↓
                              signal-agent (LangGraph + LLM)
                                          ↓
                              Redis Stream → alert-module → WebSocket
```

## Design Documents

See `quant-system-design/` for detailed architecture docs (01–11).
