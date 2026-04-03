"""
Abstract base class for infrastructure providers.

All providers must implement this interface.
"""

from abc import ABC, abstractmethod

from fabric.models import (
    CreateContainerRequest,
    CreateVMRequest,
    CreateInstanceResult,
    InstanceStatusResult,
    TaskStatusResult,
)


class FabricProvider(ABC):
    """
    Abstract provider interface for infrastructure operations.

    Implementations must provide provider-specific details (e.g., Proxmox API calls)
    while adhering to this common interface.

    Core and Pulse should never directly interact with provider implementations.
    """

    @abstractmethod
    def create_container(self, request: CreateContainerRequest) -> CreateInstanceResult:
        """
        Create a new container.

        Args:
            request: Container creation request with specification

        Returns:
            CreateInstanceResult with provider_ref for future operations

        Raises:
            ProviderError: If creation fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def create_vm(self, request: CreateVMRequest) -> CreateInstanceResult:
        """
        Create a new virtual machine.

        Args:
            request: VM creation request with specification

        Returns:
            CreateInstanceResult with provider_ref for future operations

        Raises:
            ProviderError: If creation fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def start_instance(self, provider_ref: str) -> InstanceStatusResult:
        """
        Start an instance.

        Args:
            provider_ref: Provider reference (VMID/CTID)

        Returns:
            InstanceStatusResult with current status

        Raises:
            InstanceNotFound: If instance does not exist
            ProviderError: If start fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def stop_instance(self, provider_ref: str) -> InstanceStatusResult:
        """
        Stop an instance.

        Args:
            provider_ref: Provider reference (VMID/CTID)

        Returns:
            InstanceStatusResult with current status

        Raises:
            InstanceNotFound: If instance does not exist
            ProviderError: If stop fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def reboot_instance(self, provider_ref: str) -> InstanceStatusResult:
        """
        Reboot an instance.

        Args:
            provider_ref: Provider reference (VMID/CTID)

        Returns:
            InstanceStatusResult with current status

        Raises:
            InstanceNotFound: If instance does not exist
            ProviderError: If reboot fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def delete_instance(self, provider_ref: str) -> None:
        """
        Delete an instance.

        Args:
            provider_ref: Provider reference (VMID/CTID)

        Raises:
            InstanceNotFound: If instance does not exist
            ProviderError: If deletion fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def get_instance_status(self, provider_ref: str) -> InstanceStatusResult:
        """
        Get current status of an instance.

        Args:
            provider_ref: Provider reference (VMID/CTID)

        Returns:
            InstanceStatusResult with current state

        Raises:
            InstanceNotFound: If instance does not exist
            ProviderError: If query fails
        """
        pass

    @abstractmethod
    def clone_template(
        self,
        node_id: str,
        template_id: str,
        new_name: str,
    ) -> str:
        """
        Clone a template to create a new instance reference.

        Args:
            node_id: Node to clone on
            template_id: Template ID to clone from
            new_name: Name for cloned instance

        Returns:
            New provider_ref (VMID/CTID)

        Raises:
            InstanceNotFound: If template not found
            ProviderError: If clone fails
            OperationFailed: If operation cannot complete
        """
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> TaskStatusResult:
        """
        Get status of an async task on the provider.

        Args:
            task_id: Task ID returned by async operations

        Returns:
            TaskStatusResult with task progress and status

        Raises:
            ProviderError: If task lookup fails
        """
        pass
