#!/bin/bash

# Docker cleanup script to prevent network exhaustion

echo "🧹 Cleaning up Docker resources..."

# Stop all containers
echo "Stopping all containers..."
docker stop $(docker ps -aq) 2>/dev/null || echo "No containers to stop"

# Remove all containers
echo "Removing all containers..."
docker container prune -f

# Remove unused networks
echo "Removing unused networks..."
docker network prune -f

# Remove unused volumes
echo "Removing unused volumes..."
docker volume prune -f

# Remove unused images (optional - commented out to preserve built images)
# echo "Removing unused images..."
# docker image prune -f

echo "✅ Docker cleanup completed!"
echo ""
echo "Current networks:"
docker network ls