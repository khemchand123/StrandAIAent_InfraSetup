#!/bin/bash

# Elasticsearch AI Agent API Deployment Script

set -e

echo "🚀 Deploying Elasticsearch AI Agent API..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your AWS credentials and configuration."
    echo "   Then run this script again."
    exit 1
fi

# Build and start the application
echo "🔨 Building Docker image..."
docker-compose build

echo "🚀 Starting the application..."
docker-compose up -d

# Wait for the application to start
echo "⏳ Waiting for application to start..."
sleep 10

# Check health
echo "🏥 Checking application health..."
if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ Application is healthy and running!"
    echo ""
    echo "🌐 API is available at:"
    echo "   • API Base: http://localhost:5000"
    echo "   • API Docs: http://localhost:5000/docs"
    echo "   • Health Check: http://localhost:5000/health"
    echo ""
    echo "📖 Example usage:"
    echo '   curl -X POST "http://localhost:5000/query" \'
    echo '     -H "Content-Type: application/json" \'
    echo '     -d '"'"'{"query": "List all indices"}'"'"
else
    echo "❌ Application health check failed!"
    echo "📋 Checking logs..."
    docker-compose logs --tail=20
    exit 1
fi