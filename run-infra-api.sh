#!/bin/bash

echo "🚀 Building and starting Infrastructure Deployment API..."

# Detect docker compose command and version
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    echo "📦 Found docker-compose version: $COMPOSE_VERSION"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
    COMPOSE_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    echo "📦 Found docker compose version: $COMPOSE_VERSION"
else
    echo "❌ Neither 'docker-compose' nor 'docker compose' found. Please install Docker Compose."
    exit 1
fi

# Check for old docker-compose version that might have compatibility issues
if [[ "$DOCKER_COMPOSE" == "docker-compose" ]]; then
    MAJOR_VERSION=$(echo $COMPOSE_VERSION | cut -d. -f1)
    MINOR_VERSION=$(echo $COMPOSE_VERSION | cut -d. -f2)
    
    if [[ $MAJOR_VERSION -eq 1 && $MINOR_VERSION -lt 29 ]]; then
        echo "⚠️  Warning: Old docker-compose version detected. Consider upgrading to Docker Compose v2."
    fi
fi

echo "📦 Using: $DOCKER_COMPOSE"

# Clean up any existing containers first to avoid conflicts
echo "🧹 Cleaning up existing containers..."
$DOCKER_COMPOSE -f docker-compose.infra-api.yml down --remove-orphans 2>/dev/null || true

# Remove any existing image to force rebuild
echo "🗑️  Removing existing image..."
docker rmi infra-deployment-api 2>/dev/null || true

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t infra-deployment-api . --no-cache

# Start the service
echo "🔄 Starting Infrastructure Deployment API..."
$DOCKER_COMPOSE -f docker-compose.infra-api.yml up -d

# Wait a moment for startup
sleep 10

# Check health
echo "🏥 Checking API health..."
if curl -f http://localhost:9000/health > /dev/null 2>&1; then
    echo "✅ Infrastructure Deployment API is healthy and running!"
    echo ""
    echo "🌐 API is available at:"
    echo "   • API Base: http://localhost:9000"
    echo "   • Health Check: http://localhost:9000/health"
    echo "   • Deployments: http://localhost:9000/deployments"
    echo ""
    echo "📖 Example usage:"
    echo '   curl -X POST "http://localhost:9000/deploy" \'
    echo '     -H "Content-Type: application/json" \'
    echo '     -d "{}"'
    echo ""
    echo "📋 View logs with: $DOCKER_COMPOSE -f docker-compose.infra-api.yml logs -f"
    echo "🛑 Stop with: $DOCKER_COMPOSE -f docker-compose.infra-api.yml down"
else
    echo "❌ API health check failed. Check logs with:"
    echo "   $DOCKER_COMPOSE -f docker-compose.infra-api.yml logs"
    echo ""
    echo "🔍 Troubleshooting steps:"
    echo "   1. Check container status: docker ps -a"
    echo "   2. Check logs: $DOCKER_COMPOSE -f docker-compose.infra-api.yml logs"
    echo "   3. Try manual start: docker run -p 9000:9000 infra-deployment-api"
fi