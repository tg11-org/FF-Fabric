"""
Fabric HTTP API contract for Pulse integration.

Exposes provider operations over JSON/HTTP so Pulse can execute jobs
without direct SDK coupling.
"""

from os import getenv
from typing import NoReturn, Optional

from fastapi import Body, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from fabric.exceptions import InstanceNotFound, OperationFailed, ProviderError
from fabric.models import CreateContainerRequest, CreateVMRequest
from fabric.providers import ProxmoxFabric


class CreateInstanceAPIRequest(BaseModel):
    """HTTP request for VM/container creation."""

    node_id: str = Field(..., description="Target node ID")
    hostname: str = Field(..., description="Instance hostname")
    vcpu: int = Field(..., ge=1, description="vCPU count")
    ram_mb: int = Field(..., ge=128, description="Memory in MB")
    disk_gb: int = Field(..., ge=1, description="Disk in GB")
    template_id: Optional[str] = Field(None, description="Optional template")


class LifecycleRequest(BaseModel):
    """Lifecycle payload from worker."""

    node_id: Optional[str] = Field(None, description="Node ID (optional, provider_ref usually encodes it)")


class ProvisionAPIResponse(BaseModel):
    """Provision response payload consumed by Pulse."""

    provider_ref: str
    status: str
    primary_ip: Optional[str] = None
    task_id: Optional[str] = None


class LifecycleAPIResponse(BaseModel):
    """Lifecycle response payload consumed by Pulse."""

    status: str
    task_id: Optional[str] = None


_provider: Optional[ProxmoxFabric] = None


def _build_provider() -> ProxmoxFabric:
    """Create a Proxmox provider from environment variables."""
    proxmox_url = getenv("PROXMOX_URL", "").strip()
    api_token = getenv("PROXMOX_API_TOKEN", "").strip()
    verify_ssl = getenv("PROXMOX_VERIFY_SSL", "true").lower() == "true"
    timeout_seconds = int(getenv("PROXMOX_TIMEOUT_SECONDS", "30"))

    if not proxmox_url:
        raise RuntimeError("PROXMOX_URL is required")
    if not api_token:
        raise RuntimeError("PROXMOX_API_TOKEN is required")

    return ProxmoxFabric(
        proxmox_url=proxmox_url,
        api_token=api_token,
        verify_ssl=verify_ssl,
        timeout_seconds=timeout_seconds,
    )


def get_provider() -> ProxmoxFabric:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _raise_http_from_provider_error(exc: Exception) -> NoReturn:
    """Map domain exceptions to API responses."""
    if isinstance(exc, InstanceNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (ProviderError, OperationFailed)):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


app = FastAPI(title="Fabric API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint."""
    return {"status": "ok", "service": "fabric"}


@app.post("/containers", response_model=ProvisionAPIResponse)
def create_container(request: CreateInstanceAPIRequest) -> ProvisionAPIResponse:
    """Create an LXC container via Proxmox provider."""
    try:
        provider = get_provider()
        result = provider.create_container(
            CreateContainerRequest(
                node_id=request.node_id,
                hostname=request.hostname,
                memory_mb=request.ram_mb,
                cores=request.vcpu,
                storage_gb=request.disk_gb,
                template_id=request.template_id,
            )
        )
        return ProvisionAPIResponse(
            provider_ref=result.provider_ref,
            status=result.status.value,
            primary_ip=None,
            task_id=None,
        )
    except Exception as exc:
        _raise_http_from_provider_error(exc)


@app.post("/vms", response_model=ProvisionAPIResponse)
def create_vm(request: CreateInstanceAPIRequest) -> ProvisionAPIResponse:
    """Create a QEMU VM via Proxmox provider."""
    try:
        provider = get_provider()
        result = provider.create_vm(
            CreateVMRequest(
                node_id=request.node_id,
                hostname=request.hostname,
                memory_mb=request.ram_mb,
                cores=request.vcpu,
                storage_gb=request.disk_gb,
                template_id=request.template_id,
            )
        )
        return ProvisionAPIResponse(
            provider_ref=result.provider_ref,
            status=result.status.value,
            primary_ip=None,
            task_id=None,
        )
    except Exception as exc:
        _raise_http_from_provider_error(exc)


@app.post("/instances/{provider_ref}/start", response_model=LifecycleAPIResponse)
def start_instance(provider_ref: str, request: LifecycleRequest) -> LifecycleAPIResponse:
    """Start an instance."""
    try:
        provider = get_provider()
        result = provider.start_instance(provider_ref)
        return LifecycleAPIResponse(status=result.status.value, task_id=None)
    except Exception as exc:
        _raise_http_from_provider_error(exc)


@app.post("/instances/{provider_ref}/stop", response_model=LifecycleAPIResponse)
def stop_instance(provider_ref: str, request: LifecycleRequest) -> LifecycleAPIResponse:
    """Stop an instance."""
    try:
        provider = get_provider()
        result = provider.stop_instance(provider_ref)
        return LifecycleAPIResponse(status=result.status.value, task_id=None)
    except Exception as exc:
        _raise_http_from_provider_error(exc)


@app.post("/instances/{provider_ref}/reboot", response_model=LifecycleAPIResponse)
def reboot_instance(provider_ref: str, request: LifecycleRequest) -> LifecycleAPIResponse:
    """Reboot an instance."""
    try:
        provider = get_provider()
        result = provider.reboot_instance(provider_ref)
        return LifecycleAPIResponse(status=result.status.value, task_id=None)
    except Exception as exc:
        _raise_http_from_provider_error(exc)


@app.delete("/instances/{provider_ref}", response_model=LifecycleAPIResponse)
def delete_instance(
    provider_ref: str,
    request: Optional[LifecycleRequest] = Body(default=None),
) -> LifecycleAPIResponse:
    """Delete an instance."""
    try:
        provider = get_provider()
        provider.delete_instance(provider_ref)
        return LifecycleAPIResponse(status="deleted", task_id=None)
    except Exception as exc:
        _raise_http_from_provider_error(exc)


@app.get("/instances/{provider_ref}/status", response_model=LifecycleAPIResponse)
def get_instance_status(provider_ref: str, node_id: Optional[str] = None) -> LifecycleAPIResponse:
    """Query current instance status."""
    try:
        provider = get_provider()
        result = provider.get_instance_status(provider_ref)
        return LifecycleAPIResponse(status=result.status.value, task_id=None)
    except Exception as exc:
        _raise_http_from_provider_error(exc)
