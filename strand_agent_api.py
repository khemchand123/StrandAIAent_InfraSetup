from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging
from contextlib import asynccontextmanager

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from elastic_mapping_tool import get_elastic_index_mapping
from elasticsearch_agent_prompt import ELASTICSEARCH_AGENT_SYSTEM_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for agent and MCP client
agent = None
mcp_client = None

class QueryRequest(BaseModel):
    query: str
    temperature: Optional[float] = 0.3

class QueryResponse(BaseModel):
    response: str
    status: str = "success"
    error: Optional[str] = None

def create_streamable_http_transport():
    """Create HTTP transport for MCP client"""
    import os
    # Get encoded API key from environment variable
    encoded_key = os.getenv("ES_ENCODED_KEY", "QmhMczhKa0JoSVNaRlVzNkp1U1E6RlA4X2FENFdGR2hubU5wRHZ1QjJVUQ==")
    headers = {
        "Authorization": f"ApiKey {encoded_key}",
        "Content-Type": "application/json"
    }
    # Use environment variable for MCP URL, default to localhost for development
    mcp_url = os.getenv("MCP_URL", "http://elastic-mcp-server:8080/mcp")
    #mcp_url = os.getenv("MCP_URL", "http://localhost:8080/mcp")
    return streamablehttp_client(mcp_url, headers=headers)

async def initialize_agent():
    """Initialize the AI agent with MCP tools and Bedrock model"""
    global agent, mcp_client
    
    try:
        # Create BedrockModel
        bedrock_model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name="us-east-1",
            temperature=0.3,
        )
        
        # Try to create MCP client, but don't fail if it's not available
        mcp_tools = []
        try:
            mcp_client = MCPClient(create_streamable_http_transport)
            mcp_client.__enter__()
            mcp_tools = mcp_client.list_tools_sync()
            logger.info(f"Found {len(mcp_tools)} MCP tools")
        except Exception as mcp_error:
            logger.warning(f"MCP client not available: {mcp_error}")
            logger.info("Continuing without MCP tools...")
            mcp_client = None
        
        # Process MCP tools if available
        filtered_mcp_tools = []
        if mcp_tools:
            # Debug: Check what attributes the MCP tool has
            logger.info(f"MCP tool attributes: {dir(mcp_tools[0])}")
            logger.info(f"First tool: {mcp_tools[0]}")
            
            # Filter out problematic tools - check different possible attribute names
            problematic_tools = ['get_mappings', 'esql']
            
            for tool in mcp_tools:
                # Try different attribute names that might contain the tool name
                tool_name = None
                if hasattr(tool, 'name'):
                    tool_name = tool.name
                elif hasattr(tool, '_name'):
                    tool_name = tool._name
                elif hasattr(tool, 'tool_name'):
                    tool_name = tool.tool_name
                elif hasattr(tool, '__name__'):
                    tool_name = tool.__name__
                
                logger.info(f"Tool name found: {tool_name}")
                
                if tool_name and tool_name not in problematic_tools:
                    filtered_mcp_tools.append(tool)
                elif tool_name is None:
                    # If we can't find the name, include it for now
                    filtered_mcp_tools.append(tool)
            
            logger.info(f"Original MCP tools: {len(mcp_tools)}")
            logger.info(f"Filtered out {len(mcp_tools) - len(filtered_mcp_tools)} problematic tools: {problematic_tools}")
        
        # Add your custom elastic tools to replace broken MCP functionality
        custom_elastic_tools = [get_elastic_index_mapping]
        all_tools = filtered_mcp_tools + custom_elastic_tools
        
        logger.info(f"Available tools: {len(filtered_mcp_tools)} working MCP tools + {len(custom_elastic_tools)} custom elastic tools = {len(all_tools)} total")
        
        # Create agent with filtered MCP tools and custom elastic tools using the system prompt
        agent = Agent(
            model=bedrock_model,
            tools=all_tools,
            system_prompt=ELASTICSEARCH_AGENT_SYSTEM_PROMPT
        )
        
        logger.info("Agent initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global mcp_client
    
    # Startup
    logger.info("Starting up API wrapper...")
    if not await initialize_agent():
        logger.error("Failed to initialize agent")
        raise RuntimeError("Agent initialization failed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API wrapper...")
    if mcp_client:
        try:
            mcp_client.__exit__(None, None, None)
        except Exception as e:
            logger.error(f"Error closing MCP client: {e}")

# Create FastAPI app
app = FastAPI(
    title="Elasticsearch AI Agent API",
    description="REST API wrapper for AI-powered Elasticsearch queries using AWS Bedrock",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Doc Agent API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    tools_count = 0
    if agent:
        try:
            # Try different possible attribute names for tools
            if hasattr(agent, 'tools'):
                tools_count = len(agent.tools)
            elif hasattr(agent, '_tools'):
                tools_count = len(agent._tools)
            else:
                # If no tools attribute found, just set to 0
                tools_count = 0
        except Exception:
            tools_count = 0
    
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "mcp_enabled": mcp_client is not None,
        "tools_count": tools_count
    }

@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """
    Query the Elasticsearch AI agent
    
    Args:
        request: QueryRequest containing the query string and optional temperature
    
    Returns:
        QueryResponse with the agent's response
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        logger.info(f"Processing query: {request.query}")
        
        # Update model temperature if provided
        if request.temperature != 0.3:
            agent.model.temperature = request.temperature
        
        # Execute query
        result = agent(request.query.strip())
        
        # Extract response text
        response_text = ""
        if hasattr(result, 'message') and result.message:
            content = result.message.get('content', [])
            if content and isinstance(content, list) and len(content) > 0:
                response_text = content[0].get('text', '')
        
        if not response_text:
            response_text = str(result) if result else "No response generated"
        
        logger.info("Query processed successfully")
        
        return QueryResponse(
            response=response_text,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return QueryResponse(
            response="",
            status="error",
            error=str(e)
        )

@app.post("/query-async", response_model=QueryResponse)
async def query_agent_async(request: QueryRequest):
    """
    Async version of query endpoint for better performance
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        logger.info(f"Processing async query: {request.query}")
        
        # Run agent query in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent, request.query.strip())
        
        # Extract response text
        response_text = ""
        if hasattr(result, 'message') and result.message:
            content = result.message.get('content', [])
            if content and isinstance(content, list) and len(content) > 0:
                response_text = content[0].get('text', '')
        
        if not response_text:
            response_text = str(result) if result else "No response generated"
        
        logger.info("Async query processed successfully")
        
        return QueryResponse(
            response=response_text,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Error processing async query: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return QueryResponse(
            response="",
            status="error",
            error=str(e)
        )

@app.get("/tools")
async def list_tools():
    """List available tools"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        tools_info = []
        agent_tools = []
        
        # Try to get tools from different possible attributes
        if hasattr(agent, 'tools'):
            agent_tools = agent.tools
        elif hasattr(agent, '_tools'):
            agent_tools = agent._tools
        
        for tool in agent_tools:
            tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', 'Unknown')
            tool_doc = getattr(tool, '__doc__', 'No description available')
            tools_info.append({
                "name": tool_name,
                "description": tool_doc
            })
        
        return {
            "tools": tools_info,
            "count": len(tools_info),
            "mcp_enabled": mcp_client is not None
        }
        
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)