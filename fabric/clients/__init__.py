"""
HTTP clients for infrastructure providers.

Each client handles authentication, request/response formatting, and error handling
for its respective provider.
"""

from fabric.clients.proxmox_client import ProxmoxClient

__all__ = ["ProxmoxClient"]
