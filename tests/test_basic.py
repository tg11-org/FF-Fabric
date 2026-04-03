"""
Basic tests for Fabric module structure and imports.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules and classes can be imported."""
    print("Testing imports...")

    # Test fabric module imports
    from fabric import (
        FabricProvider,
        ProxmoxFabric,
        ProxmoxClient,
        CreateContainerRequest,
        CreateVMRequest,
        CreateInstanceResult,
        InstanceStatusResult,
        TaskStatusResult,
        InstanceStatus,
        InstanceKind,
    )

    print("✓ All imports successful")

    # Test exception imports
    from fabric.exceptions import (
        FabricException,
        ProviderError,
        InstanceNotFound,
        OperationFailed,
        OperationTimeout,
    )

    print("✓ Exception imports successful")

    return True


def test_models():
    """Test that dataclass models work correctly."""
    print("\nTesting models...")

    from fabric import CreateContainerRequest, InstanceStatus, InstanceKind

    # Create a container request
    req = CreateContainerRequest(
        node_id="test-node",
        hostname="test-container",
        memory_mb=1024,
        cores=1,
        storage_gb=20,
        password="testpass123",
    )

    assert req.node_id == "test-node"
    assert req.hostname == "test-container"
    assert req.memory_mb == 1024

    print("✓ CreateContainerRequest model works")

    # Test enums
    assert InstanceStatus.RUNNING.value == "running"
    assert InstanceKind.CONTAINER.value == "container"

    print("✓ Enum models work")

    return True


def test_client_initialization():
    """Test ProxmoxClient initialization."""
    print("\nTesting ProxmoxClient initialization...")

    from fabric import ProxmoxClient
    from fabric.exceptions import ProviderError

    try:
        # Test with valid parameters
        client = ProxmoxClient(
            base_url="https://proxmox.example.com:8006",
            api_token="root@pam!tokenid=test-token-12345",
            verify_ssl=False,
            timeout_seconds=60,
        )
        print("✓ ProxmoxClient initialization successful")
        client.close()

    except Exception as e:
        print(f"✗ ProxmoxClient initialization failed: {e}")
        return False

    # Test invalid parameters
    try:
        client = ProxmoxClient(
            base_url="",
            api_token="test",
        )
        print("✗ Should have raised ValueError for empty base_url")
        return False
    except ValueError:
        print("✓ Correctly validates empty base_url")

    try:
        client = ProxmoxClient(
            base_url="https://proxmox.example.com:8006",
            api_token="invalid-token-format",
        )
        print("✗ Should have raised ValueError for invalid token format")
        return False
    except ValueError:
        print("✓ Correctly validates token format")

    return True


def test_provider_initialization():
    """Test ProxmoxFabric provider initialization."""
    print("\nTesting ProxmoxFabric initialization...")

    from fabric import ProxmoxFabric

    try:
        provider = ProxmoxFabric(
            proxmox_url="https://proxmox.example.com:8006",
            api_token="root@pam!tokenid=test-token-12345",
            verify_ssl=False,
        )
        print("✓ ProxmoxFabric initialization successful")
        print(f"  URL: {provider.proxmox_url}")
        print(f"  Client initialized: {provider.client is not None}")
        return True

    except Exception as e:
        print(f"✗ ProxmoxFabric initialization failed: {e}")
        return False


def test_abstract_methods():
    """Test that abstract methods are defined."""
    print("\nTesting abstract methods...")

    from fabric import FabricProvider

    abstract_methods = [
        "create_container",
        "create_vm",
        "start_instance",
        "stop_instance",
        "reboot_instance",
        "delete_instance",
        "get_instance_status",
        "clone_template",
        "get_task_status",
    ]

    for method in abstract_methods:
        if not hasattr(FabricProvider, method):
            print(f"✗ Missing abstract method: {method}")
            return False

    print(f"✓ All {len(abstract_methods)} abstract methods defined")
    return True


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Fabric Module Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_models,
        test_client_initialization,
        test_provider_initialization,
        test_abstract_methods,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if all(results):
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
