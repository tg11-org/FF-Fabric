"""
Proxmox provider implementation for Fabric.

Wraps the Proxmox REST API behind the FabricProvider interface.
"""

import logging
import time
import re
from datetime import datetime
from typing import Optional, Tuple

from fabric.base import FabricProvider
from fabric.models import (
    CreateContainerRequest,
    CreateVMRequest,
    CreateInstanceResult,
    InstanceStatusResult,
    InstanceStatus,
    InstanceKind,
    TaskStatusResult,
)
from fabric.exceptions import (
    ProviderError,
    InstanceNotFound,
    OperationFailed,
    OperationTimeout,
)
from fabric.clients.proxmox_client import ProxmoxClient

logger = logging.getLogger(__name__)


class ProxmoxFabric(FabricProvider):
    """
    Proxmox provider implementation.

    Manages VMs and containers on Proxmox Virtual Environment.
    Communicates via Proxmox REST API.
    """

    def __init__(
        self,
        proxmox_url: str,
        api_token: str,
        verify_ssl: bool = True,
        timeout_seconds: int = 30,
    ):
        """
        Initialize Proxmox provider.

        Args:
            proxmox_url: Proxmox API URL (e.g., https://proxmox.example.com:8006)
            api_token: API token in format "user@realm!tokenid=token"
            verify_ssl: Whether to verify SSL certificates
            timeout_seconds: Request timeout in seconds
        """
        self.proxmox_url = proxmox_url
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds

        # Initialize Proxmox API client
        self.client = ProxmoxClient(
            base_url=proxmox_url,
            api_token=api_token,
            verify_ssl=verify_ssl,
            timeout_seconds=timeout_seconds,
        )
        logger.info(f"ProxmoxFabric initialized for {proxmox_url}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _parse_upid(self, upid: str) -> Tuple[str, str]:
        """
        Parse Proxmox UPID to extract node and task id.

        UPID format: UPID:node1:00000d78:0000000000000003:1636391234:lxc:10:root

        Args:
            upid: UPID string from Proxmox

        Returns:
            Tuple of (node_name, task_id_for_polling)
        """
        try:
            parts = upid.split(":")
            if len(parts) >= 2:
                node = parts[1]
                return node, upid
        except Exception:
            pass
        return None, upid

    def _build_provider_ref(self, kind: InstanceKind, node_id: str, vmid: str) -> str:
        """
        Build an opaque provider reference that can be parsed later.

        Format: {kind}:{node_id}:{vmid}
        Example: lxc:node1:100 or qemu:node1:200

        Args:
            kind: Instance kind (container or vm)
            node_id: Proxmox node name
            vmid: VM/Container ID

        Returns:
            Opaque provider reference string
        """
        kind_str = "lxc" if kind == InstanceKind.CONTAINER else "qemu"
        return f"{kind_str}:{node_id}:{vmid}"

    def _parse_provider_ref(self, provider_ref: str) -> Tuple[str, str, str]:
        """
        Parse provider reference back into components.

        Args:
            provider_ref: Opaque provider reference from earlier call

        Returns:
            Tuple of (kind_name, node_id, vmid)
            kind_name will be "lxc" or "qemu"

        Raises:
            ValueError: If provider_ref format is invalid
        """
        try:
            parts = provider_ref.split(":")
            if len(parts) != 3:
                raise ValueError(f"Invalid provider_ref format: {provider_ref}")
            kind_name, node_id, vmid = parts
            if kind_name not in ("lxc", "qemu"):
                raise ValueError(f"Unknown kind in provider_ref: {kind_name}")
            return kind_name, node_id, vmid
        except ValueError as e:
            raise ValueError(f"Failed to parse provider_ref '{provider_ref}': {str(e)}")

    def _poll_task(
        self,
        node_id: str,
        upid: str,
        timeout_seconds: int = 300,
        poll_interval: float = 2.0,
    ) -> dict:
        """
        Poll a Proxmox task until completion.

        Args:
            node_id: Node where task is running
            upid: UPID (task ID) to poll
            timeout_seconds: Maximum time to wait (default 5 minutes)
            poll_interval: Seconds between polls (default 2 seconds)

        Returns:
            Final task status dict

        Raises:
            OperationTimeout: If task doesn't complete within timeout
            OperationFailed: If task fails
        """
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout_seconds:
            try:
                response = self.client.get(f"/api2/json/nodes/{node_id}/tasks/{upid}/status")
                last_status = response.get("data", {})

                status = last_status.get("status", "unknown")
                logger.debug(f"Task {upid} status: {status}")

                if status == "stopped":
                    # Task completed
                    exit_status = last_status.get("exitstatus", "unknown")
                    if exit_status == "OK":
                        logger.info(f"Task {upid} completed successfully")
                        return last_status
                    else:
                        raise OperationFailed(
                            operation="task_execution",
                            provider_ref=upid,
                            reason=f"Task failed with exit status: {exit_status}",
                        )

                # Task still running
                time.sleep(poll_interval)

            except ProviderError as e:
                # If task not found, assume it's very quick and completed
                if "404" in str(e.provider_code):
                    logger.info(f"Task {upid} not found (likely completed quickly)")
                    return last_status or {"status": "stopped", "exitstatus": "OK"}
                raise

        # Timeout
        raise OperationTimeout(
            operation="task_polling",
            provider_ref=upid,
            timeout_seconds=timeout_seconds,
        )

    def _extract_vmid_from_response(self, response: dict) -> str:
        """
        Extract VMID/CTID from task response.

        Proxmox async operations return task info, which we need to extract
        the actual VM/CT id from.

        Args:
            response: Response dict from Proxmox API

        Returns:
            VM/CT ID as string
        """
        # The response might have the upid directly
        upid = response.get("data", "")
        if upid and isinstance(upid, str):
            # UPID format: UPID:node:... try to extract from response dict
            # Sometimes the response has the VMID as a separate field
            pass

        # Try alternate locations
        if isinstance(response.get("data"), dict):
            data = response.get("data", {})
            return str(data.get("vmid") or data.get("id") or data.get("ctid") or "")

        return ""

    def _get_instance_status_internal(
        self, node_id: str, kind_name: str, vmid: str
    ) -> InstanceStatusResult:
        """
        Query Proxmox for current instance status (internal helper).

        Args:
            node_id: Node name
            kind_name: "lxc" or "qemu"
            vmid: VM/Container ID

        Returns:
            InstanceStatusResult with current state

        Raises:
            InstanceNotFound: If instance not found
            ProviderError: If query fails
        """
        try:
            # Query current status
            response = self.client.get(
                f"/api2/json/nodes/{node_id}/{kind_name}/{vmid}/status/current"
            )

            data = response.get("data", {})
            status_str = data.get("status", "unknown")

            # Map Proxmox status to our enum
            status_map = {
                "running": InstanceStatus.RUNNING,
                "stopped": InstanceStatus.STOPPED,
                "paused": InstanceStatus.PAUSED,
                "unknown": InstanceStatus.UNKNOWN,
            }
            status = status_map.get(status_str, InstanceStatus.UNKNOWN)

            # Extract info
            kind = InstanceKind.CONTAINER if kind_name == "lxc" else InstanceKind.VM
            hostname = data.get("hostname") or data.get("name", "")
            memory_mb = data.get("maxmem", 0) // (1024 * 1024) if data.get("maxmem") else None
            cores = data.get("cpus") or data.get("cores")
            disk_gb = data.get("maxdisk", 0) // (1024 * 1024 * 1024) if data.get("maxdisk") else None
            uptime_seconds = data.get("uptime")

            return InstanceStatusResult(
                provider_ref=self._build_provider_ref(kind, node_id, vmid),
                node_id=node_id,
                kind=kind,
                hostname=hostname,
                status=status,
                memory_mb=memory_mb,
                cores=cores,
                disk_gb=disk_gb,
                uptime_seconds=uptime_seconds,
            )

        except ProviderError as e:
            if "404" in str(e.provider_code):
                raise InstanceNotFound(
                    f"{kind_name}:{node_id}:{vmid}"
                )
            raise

    def create_container(self, request: CreateContainerRequest) -> CreateInstanceResult:
        """
        Create a new LXC container on Proxmox.

        Args:
            request: Container creation request

        Returns:
            CreateInstanceResult with CTID (container ID)

        Raises:
            ProviderError: If Proxmox API returns error
            OperationFailed: If container creation fails
        """
        logger.info(
            f"Creating container {request.hostname} on node {request.node_id} "
            f"with {request.cores} cores, {request.memory_mb}MB RAM, "
            f"{request.storage_gb}GB disk"
        )

        # Build container creation payload
        payload = {
            "vmid": 0,  # Proxmox will auto-assign if 0, otherwise we'd get from Core
            "hostname": request.hostname,
            "memory": request.memory_mb,
            "cores": request.cores,
            "storage": "local-lvm",  # TODO: Make configurable
            "ostype": "debian",  # TODO: Make configurable
            "description": request.description or f"Created by Fabric on {datetime.utcnow().isoformat()}",
        }

        # Add optional fields
        if request.password:
            payload["password"] = request.password
        if request.ssh_key:
            payload["ssh-public-keys"] = request.ssh_key
        if request.network:
            payload["net0"] = f"name=eth0,ip={request.network},type=veth"
        if request.template_id:
            payload["ostemplate"] = request.template_id
            # Use clone method for template-based creation
            logger.info(f"Using template {request.template_id} for container")

        try:
            # Create container
            response = self.client.post(
                f"/api2/json/nodes/{request.node_id}/lxc",
                data=payload,
            )

            # Extract UPID (task ID) or CTID from response
            upid_or_id = response.get("data", "")
            logger.debug(f"Container creation response: {response}")

            # If response is a UPID, poll the task
            if upid_or_id and isinstance(upid_or_id, str) and upid_or_id.startswith("UPID:"):
                logger.info(f"Polling container creation task: {upid_or_id}")
                task_result = self._poll_task(request.node_id, upid_or_id)

                # After task completes, we need to determine the CTID
                # Try to extract from task result or query newest container
                # For now, extract from UPID
                upid_parts = upid_or_id.split(":")
                if len(upid_parts) >= 7:
                    ctid = upid_parts[6]  # UPID:node:...:...:...:lxc:ctid:...
                else:
                    # Fallback: get latest container on node
                    all_containers = self.client.get(
                        f"/api2/json/nodes/{request.node_id}/lxc"
                    )
                    if all_containers.get("data"):
                        # Get the most recent
                        latest = max(
                            all_containers["data"],
                            key=lambda x: x.get("created", 0),
                        )
                        ctid = str(latest.get("vmid", ""))
                    else:
                        raise OperationFailed(
                            operation="create_container",
                            provider_ref=request.hostname,
                            reason="Could not determine container ID after creation",
                        )
            else:
                # Synchronous response with CTID
                ctid = str(upid_or_id) if upid_or_id else ""
                if not ctid:
                    raise OperationFailed(
                        operation="create_container",
                        provider_ref=request.hostname,
                        reason="No container ID in response",
                    )

            logger.info(f"Container {request.hostname} created with CTID {ctid}")

            # Query final status
            status_result = self._get_instance_status_internal(
                request.node_id, "lxc", ctid
            )

            return CreateInstanceResult(
                provider_ref=status_result.provider_ref,
                node_id=request.node_id,
                kind=InstanceKind.CONTAINER,
                status=status_result.status,
                created_at=datetime.utcnow(),
            )

        except ProviderError as e:
            logger.error(f"Failed to create container: {e}")
            raise OperationFailed(
                operation="create_container",
                provider_ref=request.hostname,
                reason=str(e),
            )

    def create_vm(self, request: CreateVMRequest) -> CreateInstanceResult:
        """
        Create a new virtual machine on Proxmox.

        Args:
            request: VM creation request

        Returns:
            CreateInstanceResult with VMID (virtual machine ID)

        Raises:
            ProviderError: If Proxmox API returns error
            OperationFailed: If VM creation fails
        """
        logger.info(
            f"Creating VM {request.hostname} on node {request.node_id} "
            f"with {request.cores} cores, {request.memory_mb}MB RAM, "
            f"{request.storage_gb}GB disk"
        )

        # Build VM creation payload
        payload = {
            "vmid": 0,  # Proxmox will auto-assign if 0
            "name": request.hostname,
            "memory": request.memory_mb,
            "cores": request.cores,
            "sockets": 1,
            "cpu": "host",
            "description": request.description or f"Created by Fabric on {datetime.utcnow().isoformat()}",
        }

        # Add disk - use local-lvm storage
        # Format: {storage}:{size}
        payload["virtio0"] = f"local-lvm:{request.storage_gb * 1024}"  # Size in MB

        # Add network interface
        payload["net0"] = "virtio,bridge=vmbr0"

        if request.template_id:
            payload["ide2"] = request.template_id

        try:
            # Create VM
            response = self.client.post(
                f"/api2/json/nodes/{request.node_id}/qemu",
                data=payload,
            )

            # Extract UPID or VMID from response
            upid_or_id = response.get("data", "")
            logger.debug(f"VM creation response: {response}")

            # If response is a UPID, poll the task
            if upid_or_id and isinstance(upid_or_id, str) and upid_or_id.startswith("UPID:"):
                logger.info(f"Polling VM creation task: {upid_or_id}")
                task_result = self._poll_task(request.node_id, upid_or_id)

                # Extract VMID from UPID
                upid_parts = upid_or_id.split(":")
                if len(upid_parts) >= 7:
                    vmid = upid_parts[6]  # UPID:node:...:...:...:qemu:vmid:...
                else:
                    # Fallback: get latest VM on node
                    all_vms = self.client.get(
                        f"/api2/json/nodes/{request.node_id}/qemu"
                    )
                    if all_vms.get("data"):
                        latest = max(
                            all_vms["data"],
                            key=lambda x: x.get("created", 0),
                        )
                        vmid = str(latest.get("vmid", ""))
                    else:
                        raise OperationFailed(
                            operation="create_vm",
                            provider_ref=request.hostname,
                            reason="Could not determine VM ID after creation",
                        )
            else:
                # Synchronous response with VMID
                vmid = str(upid_or_id) if upid_or_id else ""
                if not vmid:
                    raise OperationFailed(
                        operation="create_vm",
                        provider_ref=request.hostname,
                        reason="No VM ID in response",
                    )

            logger.info(f"VM {request.hostname} created with VMID {vmid}")

            # Query final status
            status_result = self._get_instance_status_internal(
                request.node_id, "qemu", vmid
            )

            return CreateInstanceResult(
                provider_ref=status_result.provider_ref,
                node_id=request.node_id,
                kind=InstanceKind.VM,
                status=status_result.status,
                created_at=datetime.utcnow(),
            )

        except ProviderError as e:
            logger.error(f"Failed to create VM: {e}")
            raise OperationFailed(
                operation="create_vm",
                provider_ref=request.hostname,
                reason=str(e),
            )

    def start_instance(self, provider_ref: str) -> InstanceStatusResult:
        """
        Start a stopped instance (VM or container).

        Args:
            provider_ref: Provider reference (VMID or CTID)

        Returns:
            InstanceStatusResult with updated status

        Raises:
            InstanceNotFound: If instance does not exist
            OperationFailed: If start fails
        """
        logger.info(f"Starting instance {provider_ref}")

        try:
            kind_name, node_id, vmid = self._parse_provider_ref(provider_ref)

            # POST to start endpoint
            response = self.client.post(
                f"/api2/json/nodes/{node_id}/{kind_name}/{vmid}/status/start"
            )

            # Check if response contains a task
            upid = response.get("data", "")
            if upid and isinstance(upid, str) and upid.startswith("UPID:"):
                logger.info(f"Polling start task: {upid}")
                self._poll_task(node_id, upid)

            # Get final status
            return self._get_instance_status_internal(node_id, kind_name, vmid)

        except ValueError:
            raise InstanceNotFound(provider_ref)
        except ProviderError as e:
            if "404" in str(e.provider_code):
                raise InstanceNotFound(provider_ref)
            raise OperationFailed(
                operation="start_instance",
                provider_ref=provider_ref,
                reason=str(e),
            )

    def stop_instance(self, provider_ref: str) -> InstanceStatusResult:
        """
        Stop a running instance (VM or container).

        Args:
            provider_ref: Provider reference (VMID or CTID)

        Returns:
            InstanceStatusResult with updated status

        Raises:
            InstanceNotFound: If instance does not exist
            OperationFailed: If stop fails
        """
        logger.info(f"Stopping instance {provider_ref}")

        try:
            kind_name, node_id, vmid = self._parse_provider_ref(provider_ref)

            # POST to stop endpoint
            response = self.client.post(
                f"/api2/json/nodes/{node_id}/{kind_name}/{vmid}/status/stop"
            )

            # Check if response contains a task
            upid = response.get("data", "")
            if upid and isinstance(upid, str) and upid.startswith("UPID:"):
                logger.info(f"Polling stop task: {upid}")
                self._poll_task(node_id, upid)

            # Get final status
            return self._get_instance_status_internal(node_id, kind_name, vmid)

        except ValueError:
            raise InstanceNotFound(provider_ref)
        except ProviderError as e:
            if "404" in str(e.provider_code):
                raise InstanceNotFound(provider_ref)
            raise OperationFailed(
                operation="stop_instance",
                provider_ref=provider_ref,
                reason=str(e),
            )

    def reboot_instance(self, provider_ref: str) -> InstanceStatusResult:
        """
        Reboot an instance (VM or container).

        Args:
            provider_ref: Provider reference (VMID or CTID)

        Returns:
            InstanceStatusResult with updated status

        Raises:
            InstanceNotFound: If instance does not exist
            OperationFailed: If reboot fails
        """
        logger.info(f"Rebooting instance {provider_ref}")

        try:
            kind_name, node_id, vmid = self._parse_provider_ref(provider_ref)

            # POST to reboot endpoint
            response = self.client.post(
                f"/api2/json/nodes/{node_id}/{kind_name}/{vmid}/status/reboot"
            )

            # Check if response contains a task
            upid = response.get("data", "")
            if upid and isinstance(upid, str) and upid.startswith("UPID:"):
                logger.info(f"Polling reboot task: {upid}")
                self._poll_task(node_id, upid)

            # Get final status
            return self._get_instance_status_internal(node_id, kind_name, vmid)

        except ValueError:
            raise InstanceNotFound(provider_ref)
        except ProviderError as e:
            if "404" in str(e.provider_code):
                raise InstanceNotFound(provider_ref)
            raise OperationFailed(
                operation="reboot_instance",
                provider_ref=provider_ref,
                reason=str(e),
            )

    def delete_instance(self, provider_ref: str) -> None:
        """
        Delete an instance (VM or container).

        Args:
            provider_ref: Provider reference (VMID or CTID)

        Raises:
            InstanceNotFound: If instance does not exist
            OperationFailed: If deletion fails
        """
        logger.info(f"Deleting instance {provider_ref}")

        try:
            kind_name, node_id, vmid = self._parse_provider_ref(provider_ref)

            # DELETE instance
            response = self.client.delete(
                f"/api2/json/nodes/{node_id}/{kind_name}/{vmid}"
            )

            # Check if response contains a task to poll
            upid = response.get("data", "")
            if upid and isinstance(upid, str) and upid.startswith("UPID:"):
                logger.info(f"Polling deletion task: {upid}")
                self._poll_task(node_id, upid, timeout_seconds=600)

            logger.info(f"Instance {provider_ref} deleted successfully")

        except ValueError:
            raise InstanceNotFound(provider_ref)
        except ProviderError as e:
            if "404" in str(e.provider_code):
                raise InstanceNotFound(provider_ref)
            raise OperationFailed(
                operation="delete_instance",
                provider_ref=provider_ref,
                reason=str(e),
            )

    def get_instance_status(self, provider_ref: str) -> InstanceStatusResult:
        """
        Get current status of an instance.

        Args:
            provider_ref: Provider reference (VMID or CTID)

        Returns:
            InstanceStatusResult with current state

        Raises:
            InstanceNotFound: If instance does not exist
        """
        logger.debug(f"Getting status for instance {provider_ref}")

        try:
            kind_name, node_id, vmid = self._parse_provider_ref(provider_ref)
            return self._get_instance_status_internal(node_id, kind_name, vmid)
        except ValueError:
            raise InstanceNotFound(provider_ref)

    def clone_template(
        self,
        node_id: str,
        template_id: str,
        new_name: str,
    ) -> str:
        """
        Clone a template to create a new instance.

        Args:
            node_id: Node to clone on
            template_id: Template ID to clone from
            new_name: Name for cloned instance

        Returns:
            New provider_ref (VMID or CTID)

        Raises:
            InstanceNotFound: If template not found
            OperationFailed: If clone fails
        """
        logger.info(
            f"Cloning template {template_id} to {new_name} on node {node_id}"
        )

        try:
            # Parse template_id to get type and ID
            kind_name = "lxc"
            template_parts = template_id.split(":")
            if template_parts[0] in ("lxc", "qemu"):
                kind_name = template_parts[0]
                template_vmid = template_parts[-1]
            else:
                template_vmid = template_id

            # Clone the template
            payload = {
                "newid": 0,
                "hostname": new_name,
                "full": 0,
            }

            response = self.client.post(
                f"/api2/json/nodes/{node_id}/{kind_name}/{template_vmid}/clone",
                data=payload,
            )

            # Extract task ID
            upid = response.get("data", "")
            if upid and isinstance(upid, str) and upid.startswith("UPID:"):
                logger.info(f"Polling clone task: {upid}")
                task_result = self._poll_task(node_id, upid)

                # Extract new VMID from UPID
                upid_parts = upid.split(":")
                if len(upid_parts) >= 7:
                    new_vmid = upid_parts[6]
                else:
                    all_instances = self.client.get(
                        f"/api2/json/nodes/{node_id}/{kind_name}"
                    )
                    if all_instances.get("data"):
                        latest = max(
                            all_instances["data"],
                            key=lambda x: x.get("created", 0),
                        )
                        new_vmid = str(latest.get("vmid", ""))
                    else:
                        raise OperationFailed(
                            operation="clone_template",
                            provider_ref=template_id,
                            reason="Could not determine cloned instance ID",
                        )
            else:
                new_vmid = str(upid) if upid else ""
                if not new_vmid:
                    raise OperationFailed(
                        operation="clone_template",
                        provider_ref=template_id,
                        reason="No instance ID in clone response",
                    )

            provider_ref = self._build_provider_ref(
                InstanceKind.CONTAINER if kind_name == "lxc" else InstanceKind.VM,
                node_id,
                new_vmid,
            )
            logger.info(f"Template cloned successfully: {provider_ref}")
            return provider_ref

        except ProviderError as e:
            if "404" in str(e.provider_code):
                raise InstanceNotFound(template_id)
            raise OperationFailed(
                operation="clone_template",
                provider_ref=template_id,
                reason=str(e),
            )

    def get_task_status(self, task_id: str) -> TaskStatusResult:
        """
        Get status of an async task on Proxmox.

        Args:
            task_id: Task ID (upid format)

        Returns:
            TaskStatusResult with task progress

        Raises:
            ProviderError: If task lookup fails
        """
        logger.debug(f"Getting task status for {task_id}")

        try:
            # Parse UPID to extract node
            node_id, _ = self._parse_upid(task_id)
            if not node_id:
                raise ProviderError(
                    f"Cannot parse node from task ID: {task_id}"
                )

            # Query task status
            response = self.client.get(
                f"/api2/json/nodes/{node_id}/tasks/{task_id}/status"
            )

            data = response.get("data", {})
            status = data.get("status", "unknown")

            return TaskStatusResult(
                task_id=task_id,
                status=status,
                progress_percent=None,
                exit_status=data.get("exitstatus"),
                error_message=data.get("message") or data.get("reason"),
                started_at=datetime.fromtimestamp(data.get("starttime", 0)) if data.get("starttime") else None,
                completed_at=datetime.fromtimestamp(data.get("endtime", 0)) if data.get("endtime") else None,
            )

        except ProviderError as e:
            logger.error(f"Failed to get task status: {e}")
            raise
