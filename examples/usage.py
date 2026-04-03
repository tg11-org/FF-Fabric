"""
Example usage of Fabric provider and client.

Demonstrates how to initialize and use ProxmoxFabric and ProxmoxClient.
"""

from fabric import ProxmoxFabric, CreateContainerRequest, InstanceKind
from fabric.exceptions import ProviderError, InstanceNotFound


def example_basic_usage():
    """
    Basic example: Initialize provider and create container.
    """
    # Initialize the Proxmox provider
    fabric = ProxmoxFabric(
        proxmox_url="https://proxmox.example.com:8006",
        api_token="root@pam!tokenid=12345678-1234-1234-1234-123456789012",
        verify_ssl=True,
        timeout_seconds=30,
    )

    # Create a container request
    container_req = CreateContainerRequest(
        node_id="pve-node1",
        hostname="web-server-001",
        memory_mb=2048,
        cores=2,
        storage_gb=50,
        template_id="local:vztmpl/debian-11-standard_11.3-1_amd64.tar.zst",
    )

    try:
        # Create the container
        result = fabric.create_container(container_req)
        print(f"✓ Container created: {result.provider_ref}")
        print(f"  Node: {result.node_id}")
        print(f"  Kind: {result.kind}")
        print(f"  Status: {result.status}")
        print(f"  Created: {result.created_at}")

    except ProviderError as e:
        print(f"✗ Provider error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


def example_instance_lifecycle():
    """
    Example: Full instance lifecycle (create -> start -> status -> stop -> delete).
    """
    fabric = ProxmoxFabric(
        proxmox_url="https://proxmox.example.com:8006",
        api_token="root@pam!tokenid=12345678-1234-1234-1234-123456789012",
    )

    provider_ref = "100"  # Assume CTID 100 exists

    try:
        # Start the instance
        print("Starting instance...")
        status = fabric.start_instance(provider_ref)
        print(f"✓ Instance started: {status.status}")

        # Check status periodically
        print("Checking status...")
        status = fabric.get_instance_status(provider_ref)
        print(f"✓ Instance status: {status.status}")
        print(f"  IP: {status.ip_address}")
        print(f"  Uptime: {status.uptime_seconds}s")

        # Stop the instance
        print("Stopping instance...")
        status = fabric.stop_instance(provider_ref)
        print(f"✓ Instance stopped: {status.status}")

        # Delete the instance
        print("Deleting instance...")
        fabric.delete_instance(provider_ref)
        print(f"✓ Instance deleted")

    except InstanceNotFound as e:
        print(f"✗ Instance not found: {e}")
    except ProviderError as e:
        print(f"✗ Provider error: {e}")


def example_context_manager():
    """
    Example: Using ProxmoxClient with context manager for automatic cleanup.
    """
    from fabric import ProxmoxClient

    try:
        with ProxmoxClient(
            base_url="https://proxmox.example.com:8006",
            api_token="root@pam!tokenid=12345678-1234-1234-1234-123456789012",
        ) as client:
            # Get list of nodes
            nodes_response = client.get("/api2/json/nodes")
            print(f"✓ Nodes: {nodes_response}")

            # Get cluster status
            cluster_response = client.get("/api2/json/cluster/status")
            print(f"✓ Cluster: {cluster_response}")

    except ProviderError as e:
        print(f"✗ API error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Fabric Provider Examples")
    print("=" * 60)

    print("\n1. Basic Usage (Create Container)")
    print("-" * 60)
    # example_basic_usage()  # Uncomment to run against actual Proxmox

    print("\n2. Instance Lifecycle")
    print("-" * 60)
    # example_instance_lifecycle()  # Uncomment to run against actual Proxmox

    print("\n3. Context Manager Usage")
    print("-" * 60)
    # example_context_manager()  # Uncomment to run against actual Proxmox

    print("\n" + "=" * 60)
    print("Note: Examples commented out - configure with real Proxmox URL")
    print("=" * 60)
