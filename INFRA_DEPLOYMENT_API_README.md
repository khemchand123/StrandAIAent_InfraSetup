# Dynamic Docker Compose Wrapper API

This wrapper API allows you to dynamically deploy your Elasticsearch + MCP + AI Agent stack with custom or auto-assigned port numbers.

## Features

- **Dynamic Port Assignment**: Automatically finds available ports or uses your specified ports
- **Multiple Instances**: Deploy multiple instances of your application simultaneously
- **Instance Management**: Start, stop, and monitor deployments
- **Health Checks**: Monitor deployment status and get logs
- **Unique Instances**: Each deployment gets a unique ID and isolated resources

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r wrapper_requirements.txt
   ```

2. **Make sure Docker and Docker Compose are installed**

3. **Start the wrapper API:**
   ```bash
   python infra_deployment_api.py
   ```
   The API will start on `http://localhost:8000`

## API Endpoints

### Deploy New Instance
```bash
POST /deploy
```

**With specific ports:**
```bash
curl -X POST http://localhost:8000/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "ports": {
      "elasticsearch_port": 7001,
      "elasticsearch_transport_port": 7002,
      "mcp_port": 7003,
      "ai_agent_port": 7004
    }
  }'
```

**With auto-assigned ports:**
```bash
curl -X POST http://localhost:8000/deploy
```

**Response:**
```json
{
  "message": "Deployment started successfully",
  "instance_id": "a1b2c3d4",
  "ports": {
    "elasticsearch": 9201,
    "elasticsearch_transport": 9301,
    "mcp_server": 8081,
    "ai_agent": 5001
  },
  "endpoints": {
    "elasticsearch": "http://localhost:9201",
    "mcp_server": "http://localhost:8081",
    "ai_agent": "http://localhost:5001"
  },
  "status": "deploying"
}
```

### List All Deployments
```bash
GET /deployments
```

### Get Deployment Info
```bash
GET /deployments/{instance_id}
```

### Stop Deployment
```bash
POST /deployments/{instance_id}/stop
```

### Get Deployment Logs
```bash
GET /deployments/{instance_id}/logs
```

### Health Check
```bash
GET /health
```

## Usage Examples

### 1. Deploy with Reserved Ports
```python
import requests

# Deploy with your reserved ports
response = requests.post('http://localhost:8000/deploy', json={
    "ports": {
        "elasticsearch_port": 9200,
        "mcp_port": 8080,
        "ai_agent_port": 5000
    }
})

deployment = response.json()
instance_id = deployment['instance_id']
print(f"Deployed instance: {instance_id}")
print(f"Elasticsearch: {deployment['endpoints']['elasticsearch']}")
print(f"MCP Server: {deployment['endpoints']['mcp_server']}")
print(f"AI Agent: {deployment['endpoints']['ai_agent']}")
```

### 2. Deploy with Auto Ports
```python
import requests

# Let the system find available ports
response = requests.post('http://localhost:8000/deploy')
deployment = response.json()

print(f"Auto-assigned ports:")
print(f"Elasticsearch: {deployment['ports']['elasticsearch']}")
print(f"MCP Server: {deployment['ports']['mcp_server']}")
print(f"AI Agent: {deployment['ports']['ai_agent']}")
```

### 3. Monitor Deployment
```python
import requests
import time

# Check deployment status
response = requests.get(f'http://localhost:8000/deployments/{instance_id}')
status = response.json()['status']

# Wait for deployment to be ready
while status == 'deploying':
    time.sleep(5)
    response = requests.get(f'http://localhost:8000/deployments/{instance_id}')
    status = response.json()['status']

print(f"Deployment status: {status}")
```

### 4. Stop Deployment
```python
import requests

# Stop the deployment
response = requests.post(f'http://localhost:8000/deployments/{instance_id}/stop')
print("Deployment stopped")
```

## Testing

Run the test script to see the wrapper API in action:

```bash
python test_wrapper.py
```

## How It Works

1. **Template System**: Uses `docker-compose.template.yml` with placeholders
2. **Port Management**: Automatically checks port availability
3. **Instance Isolation**: Each deployment gets unique container names and networks
4. **Background Processing**: Deployments run asynchronously
5. **State Management**: Tracks all active deployments in memory

## File Structure

- `infra_deployment_api.py` - Main infrastructure deployment API server
- `docker-compose.template.yml` - Template for dynamic deployments
- `test_infra_deployment.py` - Test client for the infrastructure deployment API
- `wrapper_requirements.txt` - Python dependencies

## Port Assignment Logic

1. If you provide specific ports, the API checks if they're available
2. If ports are not available, returns an error
3. If no ports specified, automatically finds 4 consecutive available ports starting from 9000
4. Each instance gets isolated networks and volumes using the instance ID

This wrapper API gives you complete control over port assignment while handling all the Docker Compose complexity automatically!