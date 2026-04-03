"""
Typed request and response models for Fabric provider operations.

These dataclasses provide a standardized interface between Core/Pulse
and the underlying infrastructure providers.
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum
from datetime import datetime


class InstanceStatus(str, Enum):
    """Possible states of an instance."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    PROVISIONING = "provisioning"
    ERROR = "error"
    UNKNOWN = "unknown"


class InstanceKind(str, Enum):
    """Type of instance."""

    CONTAINER = "container"
    VM = "vm"


@dataclass
class CreateContainerRequest:
    """Request to create a new container."""

    node_id: str
    """Proxmox node name to create container on"""

    hostname: str
    """Container hostname"""

    memory_mb: int
    """Memory allocation in MB"""

    cores: int
    """Number of CPU cores to allocate"""

    storage_gb: int
    """Disk storage in GB"""

    template_id: Optional[str] = None
    """Template ID to clone from"""

    password: Optional[str] = None
    """Root password for container"""

    ssh_key: Optional[str] = None
    """SSH public key to install"""

    network: Optional[str] = None
    """Network configuration (CIDR notation)"""

    description: Optional[str] = None
    """Container description"""


@dataclass
class CreateVMRequest:
    """Request to create a new virtual machine."""

    node_id: str
    """Proxmox node name to create VM on"""

    hostname: str
    """VM hostname"""

    memory_mb: int
    """Memory allocation in MB"""

    cores: int
    """Number of CPU cores to allocate"""

    storage_gb: int
    """Disk storage in GB"""

    template_id: Optional[str] = None
    """Template ID to clone from"""

    description: Optional[str] = None
    """VM description"""


@dataclass
class CreateInstanceResult:
    """Result of creating an instance."""

    provider_ref: str
    """Provider reference (VMID or CTID) for future operations"""

    node_id: str
    """Node instance was created on"""

    kind: InstanceKind
    """Type of instance created"""

    status: InstanceStatus
    """Initial status of the created instance"""

    created_at: datetime
    """Timestamp when instance was created"""


@dataclass
class InstanceStatusResult:
    """Result of querying instance status."""

    provider_ref: str
    """Provider reference (VMID or CTID)"""

    node_id: str
    """Node instance is on"""

    kind: InstanceKind
    """Type of instance"""

    hostname: Optional[str] = None
    """Instance hostname"""

    status: InstanceStatus = InstanceStatus.UNKNOWN
    """Current instance status"""

    memory_mb: Optional[int] = None
    """Current memory allocation in MB"""

    cores: Optional[int] = None
    """Number of CPU cores allocated"""

    disk_gb: Optional[int] = None
    """Disk allocation in GB"""

    ip_address: Optional[str] = None
    """Primary IP address if available"""

    uptime_seconds: Optional[int] = None
    """Seconds instance has been running (if running)"""

    last_updated: datetime = None
    """When this status was last queried"""

    def __post_init__(self):
        """Set default last_updated if not provided."""
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()


@dataclass
class TaskStatusResult:
    """Result of querying a task/job status."""

    task_id: str
    """Provider task ID"""

    status: str
    """Task status (running/success/error)"""

    progress_percent: Optional[int] = None
    """Progress percentage if applicable"""

    exit_status: Optional[str] = None
    """Exit status for completed tasks"""

    error_message: Optional[str] = None
    """Error message if task failed"""

    started_at: Optional[datetime] = None
    """When task started"""

    completed_at: Optional[datetime] = None
    """When task completed"""
