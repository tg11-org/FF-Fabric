# Quick Start Guide

## 1. Installation

```bash
cd Fabric
pip install -r requirements.txt
```

## 2. Configure Proxmox Connection

Create a `.env` file:

```
PROXMOX_URL=https://proxmox.example.com:8006
PROXMOX_API_TOKEN=root@pam!tokenid=12345678-1234-1234-1234-123456789012
```

Or pass directly to code:

```python
from fabric import ProxmoxFabric

fabric = ProxmoxFabric(
    proxmox_url="https://proxmox.example.com:8006",
    api_token="root@pam!tokenid=..."
)
```

## 3. Basic Operation

### List Nodes

```python
from fabric import ProxmoxClient

with ProxmoxClient(...) as client:
    response = client.get("/api2/json/nodes")
    for node in response['data']:
        print(f"{node['node']}: {node['status']}")
```

### Create Container (Once Implemented)

```python
from fabric import ProxmoxFabric, CreateContainerRequest

fabric = ProxmoxFabric(...)

result = fabric.create_container(CreateContainerRequest(
    node_id="pve-node1",
    hostname="web-001",
    memory_mb=2048,
    cores=2,
    storage_gb=50,
))

print(f"Created: {result.provider_ref}")
print(f"Status: {result.status}")
```

### Get Instance Status (Once Implemented)

```python
status = fabric.get_instance_status("100")  # CTID or VMID

print(f"Status: {status.status}")
print(f"IP: {status.ip_address}")
print(f"Uptime: {status.uptime_seconds}s")
```

## 4. Error Handling

```python
from fabric import ProxmoxFabric
from fabric.exceptions import ProviderError, InstanceNotFound

fabric = ProxmoxFabric(...)

try:
    fabric.start_instance("invalid-id")
except InstanceNotFound:
    print("Instance doesn't exist")
except ProviderError as e:
    print(f"Provider error: {e.provider_detail}")
```

## 5. Testing

Run the test suite:

```bash
python tests/test_basic.py
```

All tests should pass:
```
Results: 5/5 tests passed
✓ All tests passed!
```

## 6. Logging

Enable debug logging to see API calls:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

fabric = ProxmoxFabric(...)  # Now shows API calls
```

Output:
```
DEBUG:fabric.clients.proxmox_client:GET https://proxmox.example.com:8006/api2/json/nodes params=None
DEBUG:fabric.clients.proxmox_client:Response: {'data': [{'node': 'pve1'...}]}
```

## 7. Common Tasks

### 1. Get All Nodes and Their VMs

```python
client = ProxmoxClient(...)

nodes = client.get("/api2/json/nodes")
for node in nodes['data']:
    node_name = node['node']
    
    # Get containers
    containers = client.get(f"/api2/json/nodes/{node_name}/lxc")
    print(f"  Containers: {len(containers['data'])}")
    
    # Get VMs
    vms = client.get(f"/api2/json/nodes/{node_name}/qemu")
    print(f"  VMs: {len(vms['data'])}")
```

### 2. Get Instance Current State

```python
status = client.get("/api2/json/nodes/pve1/lxc/100/status/current")
print(f"State: {status['data']['status']}")
print(f"Memory: {status['data']['mem']} bytes")
print(f"CPU: {status['data']['cpu'] * 100}%")
```

### 3. Search for Instance by Hostname

```python
def find_instance_by_hostname(client, hostname):
    nodes = client.get("/api2/json/nodes")
    
    for node in nodes['data']:
        # Check containers
        containers = client.get(f"/api2/json/nodes/{node['node']}/lxc")
        for ct in containers['data']:
            if ct['hostname'] == hostname:
                return ('ct', node['node'], ct['vmid'])
        
        # Check VMs
        vms = client.get(f"/api2/json/nodes/{node['node']}/qemu")
        for vm in vms['data']:
            if vm['name'] == hostname:
                return ('vm', node['node'], vm['vmid'])
    
    return None

result = find_instance_by_hostname(client, "web-001")
if result:
    kind, node, vmid = result
    print(f"Found {kind} {vmid} on {node}")
```

## 8. Development Workflow

1. **Implement method in ProxmoxFabric**
   - Replace `NotImplementedError` with real code
   - Use `self.client.get/post/delete()` for API calls
   - Parse response to typed model
   - Raise appropriate exceptions

2. **Test with a test container/VM**
   - Create a test instance on Proxmox
   - Run your implementation against it
   - Verify correct parsing and error handling

3. **Add unit tests**
   - Mock the client responses
   - Test parsing logic
   - Test error handling

4. **Update Core/Pulse**
   - Add job types for Fabric operations
   - Integrate with scheduler
   - Test full workflow

## 9. Proxmox API Tips

### Authentication
Proxmox expects: `Authorization: PVEAPIToken=user@realm!tokenid=token`

The client handles this automatically via `session.headers`.

### Response Format
Proxmox API responses always follow format:
```json
{
  "data": {
    // Response data or array
  }
}
```

Access via `response['data']`

### Task IDs (UPID)
Async operations return task IDs in format:
```
UPID:node1:00000d78:0000000000000003:1636391234:lxc:10:root
```

Poll with:
```python
status = client.get(f"/api2/json/nodes/{node}/tasks/{upid}/status")
```

### Error Responses
Proxmox returns errors as:
```json
{
  "data": null,
  "errors": "Error message here"
}
```

The client extracts this automatically.

## 10. Debugging

### Enable HTTP Logging
```python
import http.client as http_client
http_client.HTTPConnection.debuglevel = 1

# Or with urllib3
import logging
logging.getLogger("urllib3").setLevel(logging.DEBUG)
```

### Check Raw Proxmox API
Use `curl` to test Proxmox API directly:
```bash
curl -k -H "Authorization: PVEAPIToken=user@realm!tokenid=token" \
     https://proxmox.example.com:8006/api2/json/nodes
```

### Common Issues

**SSL Certificate Errors**
```python
# Disable for self-signed certs (testing only)
client = ProxmoxClient(..., verify_ssl=False)
```

**Connection Timeouts**
```python
# Increase timeout
client = ProxmoxClient(..., timeout_seconds=60)
```

**Authentication Failures**
- Verify token format: `user@realm!tokenid=token_value`
- Ensure token hasn't expired
- Check token has necessary permissions

---

For more details, see:
- `PROXMOX_CLIENT_GUIDE.md` - Client API reference
- `IMPLEMENTATION_SUMMARY.md` - Architecture overview
- `README.md` - Project structure
- `examples/usage.py` - Code examples
