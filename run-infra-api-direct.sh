#!/bin/bash

echo "🚀 Building and starting Infrastructure Deployment API (Direct Docker)..."

# Stop and remove existing container
echo "🧹 Cleaning up existing containers..."
docker stop infra-deployment-api 2>/dev/null || true
docker rm infra-deployment-api 2>/dev/null || true

# Remove existing image
echo "🗑️  Removing existing image..."
docker rmi infra-deployment-api 2>/dev/null || true

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t infra-deployment-api . --no-cache

# Start the container directly
echo "🔄 Starting Infrastructure Deployment API..."
docker run -d \
  --name infra-deployment-api \
  -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/app \
  --restart unless-stopped \
  infra-deployment-api

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
    echo "📋 View logs with: docker logs -f infra-deployment-api"
    echo "🛑 Stop with: docker stop infra-deployment-api"
else
    echo "❌ API health check failed. Check logs with:"
    echo "   docker logs infra-deployment-api"
    echo ""
    echo "🔍 Troubleshooting steps:"
    echo "   1. Check container status: docker ps -a"
    echo "   2. Check logs: docker logs infra-deployment-api"
    echo "   3. Check if port 9000 is available: netstat -tlnp | grep 9000"
fi