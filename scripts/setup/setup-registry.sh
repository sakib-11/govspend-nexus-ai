#!/bin/bash
set -e

REGISTRY_NAME=${1:-"govspend-registry"}
REGISTRY_PORT=${2:-5000}

echo "🚀 Setting up local Docker registry..."

# Check if registry exists
if docker ps -a --format '{{.Names}}' | grep -q "^$REGISTRY_NAME$"; then
    echo "⚠️  Registry already exists. Starting it..."
    docker start $REGISTRY_NAME
else
    # Create registry container
    docker run -d \
        --name $REGISTRY_NAME \
        --restart always \
        -p $REGISTRY_PORT:5000 \
        -v registry-data:/var/lib/registry \
        registry:2
    echo "✅ Registry created at localhost:$REGISTRY_PORT"
fi

# Build and tag all services
echo "📦 Building and pushing service images..."
for service in ingestion-svc detection-core scoring-svc mcp-gateway explanation-svc; do
    echo "  Building $service..."
    docker build -t localhost:$REGISTRY_PORT/govspend/$service:latest -f services/$service/Dockerfile .
    docker push localhost:$REGISTRY_PORT/govspend/$service:latest
    echo "  ✅ $service pushed"
done

echo "🎉 All images pushed to local registry"
echo "📊 Registry available at: http://localhost:$REGISTRY_PORT/v2/_catalog"
