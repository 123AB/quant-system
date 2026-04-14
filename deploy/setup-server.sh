#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo " Quant-System Server Setup"
echo "========================================="

PROJECT_DIR="/home/ubuntu/quant-system"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "[1/6] Cloning repository..."
    cd /home/ubuntu
    git clone https://github.com/123AB/quant-system.git
else
    echo "[1/6] Updating repository..."
    cd "$PROJECT_DIR"
    git pull origin master
fi

cd "$PROJECT_DIR"

echo "[2/6] Creating .env file..."
if [ ! -f docker/.env ]; then
    cp .env.example docker/.env
    echo "  -> Created docker/.env from template"
    echo "  -> IMPORTANT: Edit docker/.env to set LLM_PROVIDER and API keys"
else
    echo "  -> docker/.env already exists, skipping"
fi

echo "[3/6] Starting infrastructure (PostgreSQL + Redis)..."
cd docker
docker compose up -d postgres redis
echo "  -> Waiting for health checks..."
sleep 10
docker compose ps postgres redis

echo "[4/6] Building and starting biz-service..."
docker compose up -d --build biz-service
echo "  -> Waiting for Spring Boot startup (~60-90s on 2 vCPU)..."
sleep 30
for i in $(seq 1 12); do
    if docker compose exec biz-service curl -sf http://localhost:8081/actuator/health > /dev/null 2>&1; then
        echo "  -> biz-service is healthy!"
        break
    fi
    echo "  -> Waiting... ($((i*10))s)"
    sleep 10
done

echo "[5/6] Building and starting gateway + agents..."
docker compose up -d --build data-pipeline signal-agent gateway

echo "[6/6] Configuring Nginx..."
if [ -f "$PROJECT_DIR/deploy/nginx-quant.conf" ]; then
    sudo cp "$PROJECT_DIR/deploy/nginx-quant.conf" /etc/nginx/sites-available/quant
    sudo ln -sf /etc/nginx/sites-available/quant /etc/nginx/sites-enabled/quant
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
    echo "  -> Nginx configured and reloaded"
else
    echo "  -> WARNING: nginx-quant.conf not found"
fi

echo ""
echo "========================================="
echo " Deployment Complete!"
echo "========================================="
echo ""
docker compose ps
echo ""
echo "Test endpoints:"
echo "  curl http://150.109.37.195/health"
echo "  curl http://150.109.37.195/api/soy/futures"
echo "  curl http://150.109.37.195/api/soy/crush-margin"
echo "  curl http://150.109.37.195/api/fund/list"
