"""
Custom exceptions for Fabric provider failures.
"""


class FabricException(Exception):
    """Base exception for all Fabric-related errors."""

    pass


class ProviderError(FabricException):
    """Raised when the underlying provider (e.g., Proxmox) returns an error."""

    def __init__(
        self,
        message: str,
        provider_code: str | None = None,
        provider_detail: str | None = None,
    ):
        self.message = message
        self.provider_code = provider_code
        self.provider_detail = provider_detail
        super().__init__(
            f"{message}"
            f"{f' (code: {provider_code})' if provider_code else ''}"
            f"{f': {provider_detail}' if provider_detail else ''}"
        )


class InstanceNotFound(FabricException):
    """Raised when an instance cannot be found on the provider."""

    def __init__(self, provider_ref: str):
        self.provider_ref = provider_ref
        super().__init__(f"Instance not found: {provider_ref}")


class OperationFailed(FabricException):
    """Raised when an operation fails on the provider."""

    def __init__(self, operation: str, provider_ref: str, reason: str):
        self.operation = operation
        self.provider_ref = provider_ref
        self.reason = reason
        super().__init__(
            f"Operation '{operation}' failed for {provider_ref}: {reason}"
        )


class OperationTimeout(FabricException):
    """Raised when an operation times out."""

    def __init__(self, operation: str, provider_ref: str, timeout_seconds: int):
        self.operation = operation
        self.provider_ref = provider_ref
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Operation '{operation}' timed out for {provider_ref} "
            f"after {timeout_seconds} seconds"
        )
