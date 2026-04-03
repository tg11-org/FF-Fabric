"""
Infrastructure provider implementations.

Each provider in this package implements the FabricProvider interface
for a specific infrastructure backend (e.g., Proxmox, AWS, etc).
"""

from fabric.providers.proxmox import ProxmoxFabric

__all__ = ["ProxmoxFabric"]
