#!/usr/bin/env python3

import os
import json
import uuid
import socket
import subprocess
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Thread
import time
import requests

app = Flask(__name__)

# Store active deployments
active_deployments = {}

def is_port_available(port):
    """Check if a port is available"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False

def find_available_ports(start_port=9000, count=4):
    """Find available ports starting from start_port"""
    ports = []
    current_port = start_port
    
    while len(ports) < count:
        if is_port_available(current_port):
            ports.append(current_port)
        current_port += 1
        
        # Safety check to avoid infinite loop
        if current_port > start_port + 1000:
            raise Exception("Could not find enough available ports")
    
    return ports

def get_host_ip():
    """Get the host IP address where services are running"""
    try:
        # Try to get the IP address by connecting to a remote address
        # This will give us the local IP that would be used for external connections
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connect to a remote address (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            host_ip = s.getsockname()[0]
            return host_ip
    except Exception:
        try:
            # Fallback: get hostname and resolve it
            hostname = socket.gethostname()
            host_ip = socket.gethostbyname(hostname)
            # Avoid returning 127.0.0.1 if possible
            if host_ip != "127.0.0.1":
                return host_ip
        except Exception:
            pass
    
    # Final fallback to localhost
    return "127.0.0.1"

def create_docker_compose_file(instance_id, elasticsearch_port, elasticsearch_transport_port, mcp_port, ai_agent_port):
    """Create a docker-compose file from template with dynamic ports"""
    
    # Read template
    with open('docker-compose.template.yml', 'r') as f:
        template_content = f.read()
    
    # Generate a unique subnet octet (1-254) based on instance_id hash
    subnet_octet = (hash(instance_id) % 254) + 1
    
    # Replace placeholders
    content = template_content.replace('${INSTANCE_ID}', instance_id)
    content = content.replace('${ELASTICSEARCH_PORT}', str(elasticsearch_port))
    content = content.replace('${ELASTICSEARCH_TRANSPORT_PORT}', str(elasticsearch_transport_port))
    content = content.replace('${MCP_PORT}', str(mcp_port))
    content = content.replace('${AI_AGENT_PORT}', str(ai_agent_port))
    content = content.replace('${SUBNET_OCTET}', str(subnet_octet))
    
    # Create temporary file
    compose_file = f'docker-compose-{instance_id}.yml'
    with open(compose_file, 'w') as f:
        f.write(content)
    
    return compose_file

def run_docker_compose(compose_file, instance_id):
    """Run docker-compose up in background"""
    try:
        # First start elasticsearch and init service
        cmd = ['docker-compose', '-f', compose_file, 'up', '-d', f'elasticsearch-{instance_id}', f'elasticsearch-init-{instance_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Wait for init service to complete and get both keys
        time.sleep(30)  # Wait for init to complete
        keys = get_generated_keys(instance_id)
        
        if keys:
            api_key = keys['api_key']
            encoded_key = keys['encoded_key']
            print(f"Keys generated successfully for {instance_id}")
            
            # Update the compose file with both keys
            update_compose_with_both_keys(compose_file, api_key, encoded_key)
            
            # Now start the rest of the services
            cmd = ['docker-compose', '-f', compose_file, 'up', '-d',  f'mcp-server-{instance_id}', f'doc-agent-api-{instance_id}']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Update deployment status
        if instance_id in active_deployments:
            active_deployments[instance_id]['status'] = 'services_starting'
            active_deployments[instance_id]['docker_output'] = result.stdout
            if keys:
                active_deployments[instance_id]['elasticsearch_api_key'] = keys['api_key']
                active_deployments[instance_id]['elasticsearch_encoded_key'] = keys['encoded_key']
            
            # Start monitoring services health
            monitor_services_health(instance_id)
        
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        if instance_id in active_deployments:
            active_deployments[instance_id]['status'] = 'failed'
            active_deployments[instance_id]['error'] = e.stderr
        return False, e.stderr

def monitor_services_health(instance_id):
    """Monitor services health and update status"""
    def check_health():
        if instance_id not in active_deployments:
            return
            
        deployment = active_deployments[instance_id]
        elasticsearch_port = deployment['elasticsearch_port']
        mcp_port = deployment['mcp_port']
        ai_agent_port = deployment['ai_agent_port']
        
        # Wait a bit for services to start
        time.sleep(30)
        
        api_key_generated = True  # API key is now generated by init service
        
        try:
            # Check Elasticsearch - Use basic auth with /_cluster/health
            es_healthy = False
            try:
                response = requests.get(f'http://localhost:{elasticsearch_port}/_cluster/health', 
                                      auth=('elastic', 'changeme'), timeout=5)
                es_healthy = response.status_code == 200
                
                # API key is generated by init service automatically
                    
            except Exception as e:
                print(f"Elasticsearch health check failed for {instance_id}: {e}")
            
            # Check MCP Server - Use root endpoint instead of /health
            mcp_healthy = False
            try:
                response = requests.get(f'http://localhost:{mcp_port}/', timeout=5)
                mcp_healthy = response.status_code == 200 and 'Elasticsearch MCP server' in response.text
            except Exception as e:
                print(f"MCP Server health check failed for {instance_id}: {e}")
            
            # Check AI Agent - Keep using /health
            ai_healthy = False
            try:
                response = requests.get(f'http://localhost:{ai_agent_port}/health', timeout=5)
                ai_healthy = response.status_code == 200
            except Exception as e:
                print(f"AI Agent health check failed for {instance_id}: {e}")
            
            # Update status and restart MCP server with API key if needed
            if es_healthy and mcp_healthy and ai_healthy:
                active_deployments[instance_id]['status'] = 'running'
                active_deployments[instance_id]['services_health'] = {
                    'elasticsearch': 'healthy',
                    'mcp_server': 'healthy',
                    'ai_agent': 'healthy'
                }
            elif es_healthy and mcp_healthy:
                active_deployments[instance_id]['status'] = 'partially_running'
                active_deployments[instance_id]['services_health'] = {
                    'elasticsearch': 'healthy',
                    'mcp_server': 'healthy',
                    'ai_agent': 'starting' if not ai_healthy else 'healthy'
                }
            else:
                active_deployments[instance_id]['status'] = 'partially_running'
                active_deployments[instance_id]['services_health'] = {
                    'elasticsearch': 'healthy' if es_healthy else 'unhealthy',
                    'mcp_server': 'healthy' if mcp_healthy else 'unhealthy',
                    'ai_agent': 'healthy' if ai_healthy else 'unhealthy'
                }
                
        except Exception as e:
            active_deployments[instance_id]['status'] = 'health_check_failed'
            active_deployments[instance_id]['health_error'] = str(e)
            print(f"Health check exception for {instance_id}: {e}")
    
    # Run health check in background
    thread = Thread(target=check_health)
    thread.daemon = True
    thread.start()

def generate_api_key(instance_id, elasticsearch_port):
    """Generate Elasticsearch API key"""
    try:
        api_key_payload = {
            "name": f"aws-strand-agent-{instance_id}",
            "expiration": "30d",
            "role_descriptors": {
                "my_custom_role": {
                    "cluster": ["all"],
                    "index": [{
                        "names": ["*"],
                        "privileges": ["read", "write"]
                    }]
                }
            }
        }
        
        response = requests.post(
            f'http://localhost:{elasticsearch_port}/_security/api_key',
            json=api_key_payload,
            auth=('elastic', 'changeme'),
            timeout=10
        )
        
        if response.status_code == 200:
            api_key_data = response.json()
            encoded_key = api_key_data.get('api_key')
            
            if instance_id in active_deployments:
                active_deployments[instance_id]['elasticsearch_api_key'] = encoded_key
                active_deployments[instance_id]['api_key_generated'] = True
                print(f"API key generated successfully for {instance_id}: {encoded_key}")
                return True
        else:
            if instance_id in active_deployments:
                active_deployments[instance_id]['api_key_error'] = f"Failed to generate API key: {response.text}"
            print(f"Failed to generate API key for {instance_id}: {response.text}")
            return False
                
    except Exception as e:
        if instance_id in active_deployments:
            active_deployments[instance_id]['api_key_error'] = str(e)
        print(f"Exception generating API key for {instance_id}: {e}")
        return False

def get_generated_api_key(instance_id):
    """Get the API key generated by the init service"""
    try:
        # Check if init container completed successfully
        cmd = ['docker', 'logs', f'search_ai_elasticsearch_init_{instance_id}']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print(result)
        
        if result.returncode == 0:
            # Extract API key from logs
            for line in result.stdout.split('\n'):
                print(line)
                if 'Generated API Key: ' in line:
                    api_key = line.split('Generated API Key: ')[1].strip()
                    print(f"Found ES API key for {instance_id}: {api_key}")
                    return api_key
        
        print(f"Could not find API key in logs for {instance_id}")
        return None
        
    except Exception as e:
        print(f"Error getting API key for {instance_id}: {e}")
        return None

def get_generated_keys(instance_id):
    """Get both API key and encoded key generated by the init service"""
    try:
        # Check if init container completed successfully
        cmd = ['docker', 'logs', f'search_ai_elasticsearch_init_{instance_id}']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print(result)
        
        if result.returncode == 0:
            api_key = None
            encoded_key = None
            
            # Extract both keys from logs
            for line in result.stdout.split('\n'):
                print(line)
                if 'Generated API Key: ' in line:
                    api_key = line.split('Generated API Key: ')[1].strip()
                    print(f"Found ES API key for {instance_id}: {api_key}")
                elif 'Generated Encoded Key: ' in line:
                    encoded_key = line.split('Generated Encoded Key: ')[1].strip()
                    print(f"Found ES encoded key for {instance_id}: {encoded_key}")
            
            if api_key and encoded_key:
                return {'api_key': api_key, 'encoded_key': encoded_key}
        
        print(f"Could not find both keys in logs for {instance_id}")
        return None
        
    except Exception as e:
        print(f"Error getting API key for {instance_id}: {e}")
        return None


def update_compose_with_api_key_env(compose_file, api_key):
    """Update docker-compose file to replace ES_API_KEY placeholder with actual key"""
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Replace the placeholder with actual API key
        updated_content = content.replace('${ES_API_KEY}', api_key)
        
        with open(compose_file, 'w') as f:
            f.write(updated_content)
        
        print(f"Updated {compose_file} with API key")
        return True
        
    except Exception as e:
        print(f"Error updating compose file {compose_file}: {e}")
        return False

def update_compose_with_both_keys(compose_file, api_key, encoded_key):
    """Update docker-compose file to replace both ES_API_KEY and ES_ENCODED_KEY placeholders"""
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Replace both placeholders
        updated_content = content.replace('${ES_API_KEY}', api_key)
        updated_content = updated_content.replace('${ES_ENCODED_KEY}', encoded_key)
        
        with open(compose_file, 'w') as f:
            f.write(updated_content)
        
        print(f"Updated {compose_file} with both API key and encoded key")
        return True
        
    except Exception as e:
        print(f"Error updating compose file {compose_file}: {e}")
        return False


def update_mcp_with_api_key(instance_id):
    """Update MCP server environment with the generated API key and restart services"""
    try:
        if instance_id not in active_deployments:
            return False
            
        deployment = active_deployments[instance_id]
        api_key = deployment.get('elasticsearch_api_key')
        
        if not api_key:
            print(f"No API key available for {instance_id}")
            return False
        
        compose_file = deployment['compose_file']
        
        # With the new template, API key is handled dynamically in the container startup
        # Just restart the services to pick up the API key from the shared file
        cmd = ['docker-compose', '-f', compose_file, 'restart', f'mcp-server-{instance_id}', f'doc-agent-api-{instance_id}']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Successfully restarted services for {instance_id}")
            active_deployments[instance_id]['mcp_updated_with_api_key'] = True
            return True
        else:
            print(f"Failed to restart services for {instance_id}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Exception updating MCP with API key for {instance_id}: {e}")
        return False

@app.route('/deploy-async', methods=['POST'])
def deploy_application_async():
    """Deploy a new instance of the application with dynamic ports (async)"""
    try:
        # Get request data
        data = request.get_json() or {}
        
        # Generate unique instance ID
        instance_id = str(uuid.uuid4())[:8]
        
        # Get port preferences or find available ones
        preferred_ports = data.get('ports', {})
        
        if 'elasticsearch_port' in preferred_ports and 'mcp_port' in preferred_ports and 'ai_agent_port' in preferred_ports:
            # Use provided ports
            elasticsearch_port = preferred_ports['elasticsearch_port']
            elasticsearch_transport_port = preferred_ports.get('elasticsearch_transport_port', elasticsearch_port + 100)
            mcp_port = preferred_ports['mcp_port']
            ai_agent_port = preferred_ports['ai_agent_port']
            
            # Check if ports are available
            ports_to_check = [elasticsearch_port, elasticsearch_transport_port, mcp_port, ai_agent_port]
            for port in ports_to_check:
                if not is_port_available(port):
                    return jsonify({
                        'error': f'Port {port} is not available',
                        'instance_id': instance_id
                    }), 400
        else:
            # Find available ports automatically
            available_ports = find_available_ports()
            elasticsearch_port = available_ports[0]
            elasticsearch_transport_port = available_ports[1]
            mcp_port = available_ports[2]
            ai_agent_port = available_ports[3]
        
        # Create docker-compose file
        compose_file = create_docker_compose_file(
            instance_id, 
            elasticsearch_port, 
            elasticsearch_transport_port, 
            mcp_port, 
            ai_agent_port
        )
        
        # Get host IP for endpoints
        host_ip = get_host_ip()
        
        # Store deployment info
        deployment_info = {
            'instance_id': instance_id,
            'elasticsearch_port': elasticsearch_port,
            'elasticsearch_transport_port': elasticsearch_transport_port,
            'mcp_port': mcp_port,
            'ai_agent_port': ai_agent_port,
            'compose_file': compose_file,
            'status': 'deploying',
            'created_at': datetime.now().isoformat(),
            'endpoints': {
                'elasticsearch': f'http://{host_ip}:{elasticsearch_port}',
                'mcp_server': f'http://{host_ip}:{mcp_port}',
                'ai_agent': f'http://{host_ip}:{ai_agent_port}'
            }
        }
        
        active_deployments[instance_id] = deployment_info
        
        # Start deployment in background
        def deploy_async():
            success, output = run_docker_compose(compose_file, instance_id)
            if not success:
                print(f"Deployment failed for {instance_id}: {output}")
        
        thread = Thread(target=deploy_async)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': 'Deployment started successfully',
            'instance_id': instance_id,
            'ports': {
                'elasticsearch': elasticsearch_port,
                'elasticsearch_transport': elasticsearch_transport_port,
                'mcp_server': mcp_port,
                'ai_agent': ai_agent_port
            },
            'endpoints': deployment_info['endpoints'],
            'status': 'deploying'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/deployments', methods=['GET'])
def list_deployments():
    """List all active deployments"""
    return jsonify({
        'deployments': list(active_deployments.values())
    })

@app.route('/deployments/<instance_id>', methods=['GET'])
def get_deployment(instance_id):
    """Get specific deployment info"""
    if instance_id not in active_deployments:
        return jsonify({'error': 'Deployment not found'}), 404
    
    return jsonify(active_deployments[instance_id])

@app.route('/deployments/<instance_id>/stop', methods=['POST'])
def stop_deployment(instance_id):
    """Stop a specific deployment"""
    if instance_id not in active_deployments:
        return jsonify({'error': 'Deployment not found'}), 404
    
    try:
        deployment = active_deployments[instance_id]
        compose_file = deployment['compose_file']
        
        # Stop docker-compose
        cmd = ['docker-compose', '-f', compose_file, 'down', '-v']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Clean up compose file
        if os.path.exists(compose_file):
            os.remove(compose_file)
        
        # Remove from active deployments
        del active_deployments[instance_id]
        
        return jsonify({
            'message': 'Deployment stopped successfully',
            'instance_id': instance_id,
            'docker_output': result.stdout
        })
        
    except subprocess.CalledProcessError as e:
        return jsonify({
            'error': 'Failed to stop deployment',
            'instance_id': instance_id,
            'docker_error': e.stderr
        }), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/deployments/<instance_id>/logs', methods=['GET'])
def get_deployment_logs(instance_id):
    """Get logs for a specific deployment"""
    if instance_id not in active_deployments:
        return jsonify({'error': 'Deployment not found'}), 404
    
    try:
        deployment = active_deployments[instance_id]
        compose_file = deployment['compose_file']
        
        # Get docker-compose logs
        cmd = ['docker-compose', '-f', compose_file, 'logs', '--tail=100']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        return jsonify({
            'instance_id': instance_id,
            'logs': result.stdout
        })
        
    except subprocess.CalledProcessError as e:
        return jsonify({
            'error': 'Failed to get logs',
            'instance_id': instance_id,
            'docker_error': e.stderr
        }), 500

@app.route('/deployments/<instance_id>/generate-api-key', methods=['POST'])
def generate_api_key_endpoint(instance_id):
    """Manually generate API key and update MCP server"""
    if instance_id not in active_deployments:
        return jsonify({'error': 'Deployment not found'}), 404
    
    try:
        deployment = active_deployments[instance_id]
        elasticsearch_port = deployment['elasticsearch_port']
        
        # Generate API key
        success = generate_api_key(instance_id, elasticsearch_port)
        
        if success:
            # Update MCP server with the new API key
            mcp_updated = update_mcp_with_api_key(instance_id)
            
            return jsonify({
                'instance_id': instance_id,
                'message': 'API key generated successfully',
                'api_key': deployment.get('elasticsearch_api_key'),
                'mcp_updated': mcp_updated
            })
        else:
            return jsonify({
                'instance_id': instance_id,
                'error': 'Failed to generate API key',
                'details': deployment.get('api_key_error')
            }), 500
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'instance_id': instance_id
        }), 500

@app.route('/deployments/<instance_id>/wait', methods=['GET'])
def wait_for_deployment(instance_id):
    """Wait for deployment to be fully ready"""
    if instance_id not in active_deployments:
        return jsonify({'error': 'Deployment not found'}), 404
    
    # Get timeout from query params (default 300 seconds = 5 minutes)
    timeout = int(request.args.get('timeout', 300))
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        deployment = active_deployments[instance_id]
        status = deployment['status']
        
        if status == 'running':
            return jsonify({
                'instance_id': instance_id,
                'status': 'ready',
                'message': 'All services are running and healthy',
                'endpoints': deployment['endpoints'],
                'services_health': deployment.get('services_health', {}),
                'elasticsearch_api_key': deployment.get('elasticsearch_api_key'),
                'wait_time': time.time() - start_time
            })
        elif status == 'failed':
            return jsonify({
                'instance_id': instance_id,
                'status': 'failed',
                'error': deployment.get('error', 'Unknown error'),
                'wait_time': time.time() - start_time
            }), 500
        
        time.sleep(2)  # Check every 2 seconds
    
    # Timeout reached
    return jsonify({
        'instance_id': instance_id,
        'status': 'timeout',
        'message': f'Deployment did not complete within {timeout} seconds',
        'current_status': active_deployments[instance_id]['status'],
        'wait_time': timeout
    }), 408

@app.route('/deploy', methods=['POST'])
def deploy_application():
    """Deploy a new instance of the application synchronously - waits for completion"""
    try:
        # Get request data
        data = request.get_json() or {}
        
        # Generate unique instance ID
        instance_id = str(uuid.uuid4())[:8]
        
        # Get port preferences or find available ones
        preferred_ports = data.get('ports', {})
        
        if 'elasticsearch_port' in preferred_ports and 'mcp_port' in preferred_ports and 'ai_agent_port' in preferred_ports:
            # Use provided ports
            elasticsearch_port = preferred_ports['elasticsearch_port']
            elasticsearch_transport_port = preferred_ports.get('elasticsearch_transport_port', elasticsearch_port + 100)
            mcp_port = preferred_ports['mcp_port']
            ai_agent_port = preferred_ports['ai_agent_port']
            
            # Check if ports are available
            ports_to_check = [elasticsearch_port, elasticsearch_transport_port, mcp_port, ai_agent_port]
            for port in ports_to_check:
                if not is_port_available(port):
                    return jsonify({
                        'error': f'Port {port} is not available',
                        'instance_id': instance_id
                    }), 400
        else:
            # Find available ports automatically
            available_ports = find_available_ports()
            elasticsearch_port = available_ports[0]
            elasticsearch_transport_port = available_ports[1]
            mcp_port = available_ports[2]
            ai_agent_port = available_ports[3]
        
        # Create docker-compose file
        compose_file = create_docker_compose_file(
            instance_id, 
            elasticsearch_port, 
            elasticsearch_transport_port, 
            mcp_port, 
            ai_agent_port
        )
        
        # Get host IP for endpoints
        host_ip = get_host_ip()
        
        # Store deployment info
        deployment_info = {
            'instance_id': instance_id,
            'elasticsearch_port': elasticsearch_port,
            'elasticsearch_transport_port': elasticsearch_transport_port,
            'mcp_port': mcp_port,
            'ai_agent_port': ai_agent_port,
            'compose_file': compose_file,
            'status': 'deploying',
            'created_at': datetime.now().isoformat(),
            'endpoints': {
                'elasticsearch': f'http://{host_ip}:{elasticsearch_port}',
                'mcp_server': f'http://{host_ip}:{mcp_port}',
                'ai_agent': f'http://{host_ip}:{ai_agent_port}'
            }
        }
        
        active_deployments[instance_id] = deployment_info
        
        # Run deployment synchronously
        success, output = run_docker_compose(compose_file, instance_id)
        
        if not success:
            # Clean up on failure
            if instance_id in active_deployments:
                del active_deployments[instance_id]
            if os.path.exists(compose_file):
                os.remove(compose_file)
            
            return jsonify({
                'error': 'Deployment failed',
                'instance_id': instance_id,
                'docker_error': output
            }), 500
        
        # Wait for services to be healthy (with timeout)
        timeout = data.get('timeout', 300)  # Default 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if instance_id not in active_deployments:
                return jsonify({
                    'error': 'Deployment was removed during health check',
                    'instance_id': instance_id
                }), 500
            
            deployment = active_deployments[instance_id]
            status = deployment['status']
            
            if status == 'running':
                response_data = {
                    'message': 'Deployment completed successfully',
                    'instance_id': instance_id,
                    'ports': {
                        'elasticsearch': elasticsearch_port,
                        'elasticsearch_transport': elasticsearch_transport_port,
                        'mcp_server': mcp_port,
                        'ai_agent': ai_agent_port
                    },
                    'endpoints': deployment_info['endpoints'],
                    'status': 'running',
                    'services_health': deployment.get('services_health', {}),
                    'elasticsearch_api_key': deployment.get('elasticsearch_api_key'),
                    'elasticsearch_encoded_key': deployment.get('elasticsearch_encoded_key'),
                    'deployment_time': time.time() - start_time
                }
                
                # Log the final response to console
                print(json.dumps(response_data, indent=2))
                
                return jsonify(response_data), 201
            elif status == 'failed':
                # Clean up on failure
                if os.path.exists(compose_file):
                    os.remove(compose_file)
                
                return jsonify({
                    'error': 'Deployment failed during health check',
                    'instance_id': instance_id,
                    'deployment_error': deployment.get('error', 'Unknown error'),
                    'deployment_time': time.time() - start_time
                }), 500
            
            time.sleep(2)  # Check every 2 seconds
        
        # Timeout reached - deployment is still in progress but taking too long
        return jsonify({
            'message': 'Deployment started but did not complete within timeout',
            'instance_id': instance_id,
            'ports': {
                'elasticsearch': elasticsearch_port,
                'elasticsearch_transport': elasticsearch_transport_port,
                'mcp_server': mcp_port,
                'ai_agent': ai_agent_port
            },
            'endpoints': deployment_info['endpoints'],
            'status': active_deployments[instance_id]['status'],
            'timeout_reached': True,
            'deployment_time': timeout,
            'note': 'Deployment continues in background. Use /deployments/<id> to check status.'
        }), 202
        
    except Exception as e:
        # Clean up on exception
        if 'instance_id' in locals() and instance_id in active_deployments:
            del active_deployments[instance_id]
        if 'compose_file' in locals() and os.path.exists(compose_file):
            os.remove(compose_file)
        
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'active_deployments': len(active_deployments),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Wrapper API...")
    print("Available endpoints:")
    print("  POST /deploy - Deploy new application instance (sync)")
    print("  POST /deploy-async - Deploy new application instance (async)")
    print("  GET /deployments - List all deployments")
    print("  GET /deployments/<id> - Get deployment info")
    print("  POST /deployments/<id>/stop - Stop deployment")
    print("  GET /deployments/<id>/logs - Get deployment logs")
    print("  GET /deployments/<id>/wait - Wait for deployment to be ready")
    print("  POST /deployments/<id>/generate-api-key - Generate API key and update MCP")
    print("  GET /health - Health check")
    
    app.run(host='0.0.0.0', port=9000, debug=True)