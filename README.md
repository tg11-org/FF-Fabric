# Fabric - Infrastructure Abstraction Layer

Fabric is the infrastructure abstraction layer for Forge Foundation, providing a clean Python interface to manage compute resources across different providers (currently Proxmox).

## Architecture

Fabric follows a provider-based architecture:

- **base.py**: Abstract `FabricProvider` class defining the common interface
- **models.py**: Typed request/response dataclasses for provider inputs and outputs
- **exceptions.py**: Custom exceptions for provider failures
- **providers/proxmox.py**: Proxmox-specific implementation

## Core Principle

> Core and Pulse should not know raw Proxmox request details.

All provider-specific implementation is contained within the `providers/` package.

## Usage

```python
from fabric.providers.proxmox import ProxmoxFabric

fabric = ProxmoxFabric(
    proxmox_url="https://proxmox.example.com:8006",
    api_token="user@pam!tokenid=abcd1234..."
)

# Create a container
result = fabric.create_container(
    CreateContainerRequest(
        node_id="node1",
        hostname="web-001",
        memory_mb=2048,
        cores=2,
        storage_gb=50,
    )
)

# Start instance
fabric.start_instance(result.provider_ref)

# Check status
status = fabric.get_instance_status(result.provider_ref)
```

## Provider Methods

All providers must implement:

- `create_container(request: CreateContainerRequest) -> CreateInstanceResult`
- `start_instance(provider_ref: str) -> InstanceStatusResult`
- `stop_instance(provider_ref: str) -> InstanceStatusResult`
- `reboot_instance(provider_ref: str) -> InstanceStatusResult`
- `delete_instance(provider_ref: str) -> None`
- `get_instance_status(provider_ref: str) -> InstanceStatusResult`

## Dependencies

See `requirements.txt` for current dependency list.
