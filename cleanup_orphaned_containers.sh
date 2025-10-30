#!/bin/bash

# Cleanup script for orphaned containers
echo "🧹 Cleaning up orphaned containers..."

# Stop all search_ai containers
echo "Stopping all search_ai containers..."
docker stop $(docker ps -q --filter "name=search_ai_") 2>/dev/null || echo "No running containers to stop"

# Remove all search_ai containers
echo "Removing all search_ai containers..."
docker rm $(docker ps -aq --filter "name=search_ai_") 2>/dev/null || echo "No containers to remove"

# Remove unused volumes
echo "Removing unused volumes..."
docker volume prune -f

# Remove unused networks
echo "Removing unused networks..."
docker network prune -f

echo "✅ Cleanup completed!"

# Show current status
echo ""
echo "Current search_ai containers:"
docker ps -a --filter "name=search_ai_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"