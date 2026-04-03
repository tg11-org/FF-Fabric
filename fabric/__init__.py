"""
Fabric - Infrastructure Abstraction Layer for Forge Foundation.

Provides unified provider interface for computing resources.
"""

__version__ = "0.1.0"

from fabric.base import FabricProvider
from fabric.exceptions import (
    FabricException,
    ProviderError,
    InstanceNotFound,
    OperationFailed,
    OperationTimeout,
)
from fabric.models import (
    CreateContainerRequest,
    CreateVMRequest,
    CreateInstanceResult,
    InstanceStatusResult,
    TaskStatusResult,
    InstanceStatus,
    InstanceKind,
)
from fabric.clients import ProxmoxClient
from fabric.providers import ProxmoxFabric
from fabric.api import app

__all__ = [
    "FabricProvider",
    "ProxmoxFabric",
    "app",
    "ProxmoxClient",
    "FabricException",
    "ProviderError",
    "InstanceNotFound",
    "OperationFailed",
    "OperationTimeout",
    "CreateContainerRequest",
    "CreateVMRequest",
    "CreateInstanceResult",
    "InstanceStatusResult",
    "TaskStatusResult",
    "InstanceStatus",
    "InstanceKind",
]
