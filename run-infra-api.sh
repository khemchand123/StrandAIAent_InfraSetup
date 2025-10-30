#!/bin/bash

echo "🚀 Building and starting Infrastructure Deployment API..."

# Detect docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Neither 'docker-compose' nor 'docker compose' found. Please install Docker Compose."
    exit 1
fi

echo "📦 Using: $DOCKER_COMPOSE"

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t infra-deployment-api .

# Start the service
echo "🔄 Starting Infrastructure Deployment API..."
$DOCKER_COMPOSE -f docker-compose.infra-api.yml up -d

# Wait a moment for startup
sleep 5

# Check health
echo "🏥 Checking API health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Infrastructure Deployment API is healthy and running!"
    echo ""
    echo "🌐 API is available at:"
    echo "   • API Base: http://localhost:8000"
    echo "   • Health Check: http://localhost:8000/health"
    echo "   • Deployments: http://localhost:8000/deployments"
    echo ""
    echo "📖 Example usage:"
    echo '   curl -X POST "http://localhost:8000/deploy" \'
    echo '     -H "Content-Type: application/json" \'
    echo '     -d "{}"'
    echo ""
    echo "📋 View logs with: $DOCKER_COMPOSE -f docker-compose.infra-api.yml logs -f"
    echo "🛑 Stop with: $DOCKER_COMPOSE -f docker-compose.infra-api.yml down"
else
    echo "❌ API health check failed. Check logs with:"
    echo "   $DOCKER_COMPOSE -f docker-compose.infra-api.yml logs"
fi