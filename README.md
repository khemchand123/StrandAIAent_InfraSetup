# Elasticsearch AI Agent API

A production-ready FastAPI wrapper that provides REST API endpoints to interact with Elasticsearch data through natural language queries using AWS Bedrock (Claude AI).

## 🚀 Features

- **FastAPI-based REST API** with automatic OpenAPI documentation
- **AI-powered Elasticsearch queries** using AWS Bedrock Claude 3 Haiku
- **MCP (Model Context Protocol) integration** for advanced tool support
- **Multiple Elasticsearch tools**: List indices, get mappings, search documents
- **Structured CSV response format** for easy data consumption
- **Production-ready** with Docker support and health checks
- **Async support** for better performance
- **Comprehensive error handling** and logging

## 📋 Prerequisites

- **Python 3.11+**
- **AWS Account** with Bedrock access
- **AWS Credentials** configured (IAM role, access keys, or AWS CLI)
- **Elasticsearch cluster** accessible via the configured endpoint
- **MCP Server** running on 82.112.235.26:8080 (for enhanced tool support)

## 🛠️ Installation & Setup

### Option 1: Local Development

1. **Clone and install dependencies:**
```bash
git clone <repository>
cd DocHelpAgent
pip install -r requirements.txt
```

2. **Configure AWS credentials:**
```bash
# Option A: AWS CLI
aws configure

# Option B: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

3. **Start the API:**
```bash
python start_api.py
```

### Option 2: Docker Deployment

1. **Build and run with Docker:**
```bash
# Build the image
docker build -t elasticsearch-ai-agent .

# Run with environment variables
docker run -p 5000:5000 \
  -e AWS_ACCESS_KEY_ID=your_access_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret_key \
  -e AWS_DEFAULT_REGION=us-east-1 \
  elasticsearch-ai-agent
```

2. **Or use Docker Compose:**
```bash
# Edit docker-compose.yml to add your AWS credentials
docker-compose up -d
```

### Option 3: Production Deployment

```bash
# For production, use uvicorn directly
uvicorn api_wrapper:app --host 0.0.0.0 --port 5000 --workers 4
```

## 🌐 API Access

Once running, the API is available at:
- **API Base**: http://localhost:5000
- **Interactive Docs**: http://localhost:5000/docs
- **Health Check**: http://localhost:5000/health

## 📖 API Usage

### Health Check
```bash
curl http://localhost:5000/health
```

### Query the AI Agent
```bash
curl -X POST "http://localhost:5000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "List all indices",
    "temperature": 0.3
  }'
```

### Async Query (Recommended for production)
```bash
curl -X POST "http://localhost:5000/query-async" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Get mapping for user_notifications index",
    "temperature": 0.3
  }'
```

### List Available Tools
```bash
curl http://localhost:5000/tools
```

## 💡 Example Queries

The AI agent understands natural language queries about your Elasticsearch data:

```bash
# List all indices
"List all indices"

# Get index mapping
"Get mapping for rss_feeder_logs index"

# Search for data
"Search for recent user notifications"
"Find documents in the disaster index"
"Show me geofencing data for users"

# Get index statistics
"What's the size of the user_geo_fencing_logs index?"
"How many documents are in the stock_market_listings index?"
```

## 📊 Response Format

The AI agent returns structured CSV-like responses:

```
predata,Successfully retrieved all Elasticsearch indices
header,[Index Name, Health, Status, Document Count, Store Size]
data,[{rss_feeder_logs, green, open, 2824, 2.8mb}, {user_notifications, yellow, open, 500, 112.7kb}]
postdata,Total of 37 indices found. 15 green, 22 yellow status.
finaly,Would you like to explore specific index mappings or search for data?
```

## 🐍 Python Client Example

```python
import requests
import json

# API base URL
API_URL = "http://localhost:5000"

def query_elasticsearch_ai(query, temperature=0.3):
    """Query the Elasticsearch AI agent"""
    response = requests.post(
        f"{API_URL}/query-async",
        json={"query": query, "temperature": temperature},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        if result["status"] == "success":
            return result["response"]
        else:
            print(f"Error: {result['error']}")
    else:
        print(f"HTTP Error: {response.status_code}")
    
    return None

# Example usage
if __name__ == "__main__":
    # Check health
    health = requests.get(f"{API_URL}/health").json()
    print(f"API Status: {health['status']}")
    
    # Query examples
    queries = [
        "List all indices",
        "Get mapping for user_notifications index",
        "Search for recent documents in rss_feeder_logs"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = query_elasticsearch_ai(query)
        if response:
            print(f"Response: {response[:200]}...")
```

## 🔧 Configuration

### Elasticsearch Configuration
Edit `elastic_mapping_tool.py` to configure:
```python
elastic_endpoint = "https://your-elasticsearch-endpoint"
elastic_api_key = "your_api_key"
```

### AWS Bedrock Configuration
Edit `strand_agent_api.py` to configure:
```python
bedrock_model = BedrockModel(
    model_id="your-model-arn",
    region_name="your-region",
    temperature=0.3,
)
```

## 🚨 Error Handling

The API provides detailed error responses:

```json
{
  "response": "",
  "status": "error", 
  "error": "Detailed error message"
}
```

**Common HTTP Status Codes:**
- `200`: Success
- `400`: Bad request (empty query)
- `503`: Service unavailable (agent not initialized)
- `500`: Internal server error

## 🔍 Troubleshooting

### Agent Not Initialized
- Check AWS credentials and Bedrock permissions
- Verify the model ARN is correct and accessible
- Check AWS region configuration

### Elasticsearch Connection Issues
- Verify the Elasticsearch endpoint URL
- Check the API key permissions
- Ensure network connectivity to Elasticsearch

### Empty or Invalid Responses
- Check AWS Bedrock service limits
- Verify the model is available in your region
- Review CloudWatch logs for detailed errors

## 🏗️ Project Structure

```
├── strand_agent_api.py         # Main Strand Agent FastAPI application
├── start_api.py               # Development startup script
├── elastic_mapping_tool.py    # Elasticsearch tools and functions
├── elasticsearch_agent_prompt.py # AI system prompt
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker container configuration
├── docker-compose.yml         # Docker Compose setup
└── README.md                  # This file
```

## 🔐 Security Considerations

- **AWS Credentials**: Use IAM roles when possible, avoid hardcoding keys
- **API Access**: Consider adding authentication for production use
- **Network**: Run behind a reverse proxy (nginx) in production
- **Elasticsearch**: Ensure proper access controls on your Elasticsearch cluster

## 📈 Production Deployment

### AWS ECS/Fargate
```bash
# Build and push to ECR
docker build -t your-account.dkr.ecr.region.amazonaws.com/elasticsearch-ai-agent .
docker push your-account.dkr.ecr.region.amazonaws.com/elasticsearch-ai-agent
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: elasticsearch-ai-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: elasticsearch-ai-agent
  template:
    metadata:
      labels:
        app: elasticsearch-ai-agent
    spec:
      containers:
      - name: api
        image: elasticsearch-ai-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: AWS_DEFAULT_REGION
          value: "us-east-1"
```

## 📞 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the API documentation at `/docs`
3. Check application logs for detailed error messages
4. Verify AWS and Elasticsearch connectivity

## 📄 License

This project is part of the Elasticsearch AI agent system.