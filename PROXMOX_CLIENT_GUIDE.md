"""
Proxmox API Client Documentation and Reference.

This document explains the ProxmoxClient class and how to use it.
"""


# ============================================================================
# ProxmoxClient - Generic HTTP Client for Proxmox REST API
# ============================================================================

"""
The ProxmoxClient is a reusable HTTP client wrapper for the Proxmox Virtual
Environment (PVE) REST API. It handles:

- Token-based authentication
- HTTP request/response handling (GET, POST, DELETE)
- Automatic retries with exponential backoff
- JSON parsing and error handling
- SSL/TLS configuration
- Timeouts and connection pooling via requests.Session


FEATURES
========

1. Connection Pooling
   - Uses requests.Session for efficient connection reuse
   - Reduces overhead for multiple API calls

2. Authentication
   - Token-based auth (PVEAPIToken header format)
   - No password/username handling (safer)

3. Automatic Retries
   - Recovers from transient errors (5xx, 429)
   - Exponential backoff: 0.5s, 1s, 1.5s

4. Error Handling
   - Extracts Proxmox error messages
   - Typed exceptions (ProviderError)
   - Context for debugging


INITIALIZATION
==============

Basic:
    from fabric import ProxmoxClient

    client = ProxmoxClient(
        base_url="https://proxmox.example.com:8006",
        api_token="root@pam!tokenid=12345678-1234-1234-1234-123456789012"
    )

With custom options:
    client = ProxmoxClient(
        base_url="https://proxmox.example.com:8006",
        api_token="root@pam!tokenid=...",
        verify_ssl=False,              # Disable SSL verification
        timeout_seconds=60,             # Custom timeout
    )

Using context manager (recommended):
    with ProxmoxClient(...) as client:
        nodes = client.get("/api2/json/nodes")
    # Session automatically closed


API_TOKEN FORMAT
================

Proxmox API tokens follow format:
    user@realm!tokenid=token_value

Examples:
    root@pam!tokenid=12345678-1234-1234-1234-123456789012
    admin@pam!tokenid=abcdef01-2345-6789-abcd-ef0123456789

To generate a token in Proxmox Web UI:
    1. Datacenter > Permissions > API Tokens
    2. Click "Add API Token"
    3. Select user and give it a descriptive name
    4. Copy the full token value (includes user@realm!tokenid=...)


METHODS
=======

GET(path, params=None, timeout=None) -> dict
    Perform a GET request
    
    Args:
        path: API endpoint path (e.g., "/api2/json/nodes")
        params: Query parameters dict
        timeout: Override default timeout
    
    Returns:
        Parsed JSON response as dictionary
    
    Example:
        nodes = client.get("/api2/json/nodes")
        # Returns: {"data": [{"node": "pve1", ...}]}


POST(path, data=None, params=None, timeout=None) -> dict
    Perform a POST request
    
    Args:
        path: API endpoint path
        data: Request body dict (sent as JSON)
        params: Query parameters dict
        timeout: Override default timeout
    
    Returns:
        Parsed JSON response as dictionary
    
    Example:
        result = client.post(
            "/api2/json/nodes/pve1/lxc",
            data={
                "vmid": 100,
                "hostname": "container1",
                "memory": 2048,
            }
        )


DELETE(path, params=None, timeout=None) -> dict
    Perform a DELETE request
    
    Args:
        path: API endpoint path
        params: Query parameters dict
        timeout: Override default timeout
    
    Returns:
        Parsed JSON response as dictionary
    
    Example:
        result = client.delete("/api2/json/nodes/pve1/lxc/100")


COMMON PROXMOX ENDPOINTS
========================

Cluster & Nodes:
    GET /api2/json/nodes
    GET /api2/json/nodes/{node}
    GET /api2/json/cluster/status

Containers (LXC):
    GET /api2/json/nodes/{node}/lxc
    POST /api2/json/nodes/{node}/lxc
    GET /api2/json/nodes/{node}/lxc/{ctid}
    POST /api2/json/nodes/{node}/lxc/{ctid}/status/start
    POST /api2/json/nodes/{node}/lxc/{ctid}/status/stop
    DELETE /api2/json/nodes/{node}/lxc/{ctid}

Virtual Machines (QEMU):
    GET /api2/json/nodes/{node}/qemu
    POST /api2/json/nodes/{node}/qemu
    GET /api2/json/nodes/{node}/qemu/{vmid}
    POST /api2/json/nodes/{node}/qemu/{vmid}/status/start
    POST /api2/json/nodes/{node}/qemu/{vmid}/status/stop
    DELETE /api2/json/nodes/{node}/qemu/{vmid}

Tasks:
    GET /api2/json/nodes/{node}/tasks
    GET /api2/json/nodes/{node}/tasks/{upid}/status


USAGE EXAMPLES
==============

Example 1: List all nodes
    client = ProxmoxClient("https://proxmox.example.com:8006", token)
    response = client.get("/api2/json/nodes")
    for node in response['data']:
        print(f"Node: {node['node']}, Status: {node['status']}")


Example 2: Create a container
    response = client.post(
        "/api2/json/nodes/pve1/lxc",
        data={
            "vmid": 100,
            "hostname": "web-01",
            "memory": 2048,
            "cores": 2,
            "storage": "local-lvm",
            "ostype": "debian",
        }
    )
    print(f"Task started: {response['data']}")


Example 3: Start instance
    response = client.post(
        "/api2/json/nodes/pve1/lxc/100/status/start"
    )
    print(f"Instance started")


Example 4: Get instance status
    response = client.get("/api2/json/nodes/pve1/lxc/100/status/current")
    status = response['data']
    print(f"Status: {status['status']}, Uptime: {status.get('uptime', 'N/A')}")


ERROR HANDLING
==============

The client raises ProviderError for API failures:

    from fabric import ProxmoxClient
    from fabric.exceptions import ProviderError

    try:
        response = client.get("/api2/json/nodes/invalid")
    except ProviderError as e:
        print(f"Error: {e.message}")
        print(f"Code: {e.provider_code}")
        print(f"Detail: {e.provider_detail}")

Common error codes:
    401: Authentication failed (invalid/expired token)
    403: Permission denied (insufficient permissions)
    404: Resource not found (instance/node doesn't exist)
    5xx: Server errors (automatically retried)


PROXMOXFABRIC INTEGRATION
==========================

The ProxmoxFabric provider uses ProxmoxClient internally:

    from fabric import ProxmoxFabric, CreateContainerRequest

    fabric = ProxmoxFabric(
        proxmox_url="https://proxmox.example.com:8006",
        api_token="root@pam!tokenid=..."
    )

    # Internally:
    # - fabric.client = ProxmoxClient(...)
    # - Methods like create_container() use fabric.client.post()
    # - Methods like get_instance_status() use fabric.client.get()


PERFORMANCE CONSIDERATIONS
==========================

1. Connection Pooling
   The session reuses HTTP connections across multiple requests.
   For many operations, create one ProxmoxFabric/ProxmoxClient instance
   and reuse it rather than creating new ones repeatedly.

2. Timeouts
   Default: 30 seconds per request
   Can override per-method or override in __init__

3. Retries
   Automatic retries for transient failures (5xx errors, 429 rate limit)
   Uses exponential backoff: won't hammer a struggling server

4. SSL Verification
   Enable in production, disable for self-signed certs in testing
   verify_ssl=True (default) / verify_ssl=False (insecure)


THREAD SAFETY
=============

The requests.Session (via ProxmoxClient) is thread-safe for concurrent GET
requests. However, for safety, consider:

- One client instance per thread, or
- Use locks if sharing a client across threads

Example (concurrent usage):
    from concurrent.futures import ThreadPoolExecutor
    
    with ProxmoxClient(...) as client:
        nodes = client.get("/api2/json/nodes")
    
    # Each thread creates its own client:
    def get_node_info(node_name):
        client = ProxmoxClient(...)
        return client.get(f"/api2/json/nodes/{node_name}")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(get_node_info, node_names)
"""
