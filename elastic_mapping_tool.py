
import aiohttp
import json
from strands import tool

elastic_endpoint = "https://backend.lehana.in/elastic"
elastic_api_key = "QmhMczhKa0JoSVNaRlVzNkp1U1E6RlA4X2FENFdGR2hubU5wRHZ1QjJVUQ=="


@tool
async def get_elastic_index_mapping(index_name: str = "*") -> str:
    """Get Elasticsearch index mapping for specified index or all indices.
    
    Args:
        index_name: Name of the index to get mapping for. Use '*' for all indices.
    
    Returns:
        JSON string containing the index mapping information.
    """
    try:
        url = f"{elastic_endpoint}/{index_name}/_mapping"
        
        # Create headers with API key
        headers = {"Authorization": f"ApiKey {elastic_api_key}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    mapping_data = await response.json()
                    return json.dumps(mapping_data, indent=2)
                else:
                    error_text = await response.text()
                    return f"Error getting mapping for index '{index_name}': {response.status} - {error_text}"
                    
    except Exception as e:
        return f"Failed to get Elasticsearch mapping: {str(e)}"

