#!/bin/bash
# GraphRAG CD Deploy Script
# enterprise-evolution-blueprint-v1.0 §7.3
#
# Usage:
#   REGISTRY=ghcr.io/org/graphrag TAG=latest ./deploy/cd-deploy.sh
#   REGISTRY=ghcr.io/org/graphrag TAG=a1b2c3d ./deploy/cd-deploy.sh

set -e

REGISTRY="${REGISTRY:-ghcr.io/org/graphrag}"
TAG="${1:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

echo "========================================="
echo " GraphRAG CD Deploy"
echo " Registry: ${REGISTRY}"
echo " Tag:      ${TAG}"
echo " Compose:  ${COMPOSE_FILE}"
echo "========================================="

# Pull latest images
echo "[CD] Pulling backend image..."
docker pull "${REGISTRY}/graphrag-backend:${TAG}"

echo "[CD] Pulling frontend image..."
docker pull "${REGISTRY}/graphrag-frontend:${TAG}"

# Export TAG so docker-compose can use it
export TAG

# Restart services
echo "[CD] Restarting services..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# Wait for health check
echo "[CD] Waiting for backend health check..."
MAX_WAIT=60
INTERVAL=2
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo ""
        echo "========================================="
        echo " Deploy SUCCESS — backend healthy"
        echo " Health: $(curl -s http://localhost:8000/api/v1/health | head -c 200)"
        echo " Elapsed: ${ELAPSED}s"
        echo "========================================="
        exit 0
    fi
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
    echo -n "."
done

echo ""
echo "========================================="
echo " Deploy FAILED — backend did not become healthy within ${MAX_WAIT}s"
echo " Check logs: docker compose logs backend"
echo "========================================="
exit 1
