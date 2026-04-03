"""
Integration tests for ProxmoxFabric provider.

Tests the full workflow of container/VM creation, lifecycle operations,
and status queries using mocked Proxmox API responses.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fabric import (
    ProxmoxFabric,
    CreateContainerRequest,
    CreateVMRequest,
    InstanceStatus,
    InstanceKind,
)
from fabric.exceptions import InstanceNotFound, OperationFailed


class TestProxmoxFabricIntegration:
    """Integration tests for ProxmoxFabric provider."""

    @staticmethod
    def create_mock_client():
        """Create a mocked ProxmoxFabric with mocked client."""
        with patch('fabric.providers.proxmox.ProxmoxClient'):
            fabric = ProxmoxFabric(
                proxmox_url="https://proxmox.example.com:8006",
                api_token="root@pam!tokenid=test",
                verify_ssl=False,
            )
        return fabric

    def test_create_container_sync_response(self):
        """Test creating a container with synchronous response."""
        print("Testing create_container with sync response...")

        fabric = self.create_mock_client()

        # Mock the client post method to return a CTID directly
        fabric.client.post = Mock(return_value={"data": "100"})
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "stopped",
                "hostname": "test-container",
                "maxmem": 2147483648,  # 2GB in bytes
                "uptime": 0,
            }
        })

        # Create container
        request = CreateContainerRequest(
            node_id="pve-node1",
            hostname="test-container",
            memory_mb=2048,
            cores=2,
            storage_gb=50,
        )

        result = fabric.create_container(request)

        # Verify
        assert result.provider_ref == "lxc:pve-node1:100"
        assert result.node_id == "pve-node1"
        assert result.kind == InstanceKind.CONTAINER
        print("✓ Create container (sync) works")

    def test_create_container_async_response(self):
        """Test creating a container with async task response."""
        print("Testing create_container with async response...")

        fabric = self.create_mock_client()

        # Mock with UPID response
        upid = "UPID:pve-node1:00000d78:0000000000000003:1636391234:lxc:100:root"
        fabric.client.post = Mock(return_value={"data": upid})

        # Mock task polling
        fabric._poll_task = Mock(return_value={"status": "stopped", "exitstatus": "OK"})

        # Mock status query
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "stopped",
                "hostname": "test-container",
                "maxmem": 2147483648,
                "uptime": 0,
            }
        })

        request = CreateContainerRequest(
            node_id="pve-node1",
            hostname="test-container",
            memory_mb=2048,
            cores=2,
            storage_gb=50,
        )

        result = fabric.create_container(request)

        # Verify
        assert result.provider_ref == "lxc:pve-node1:100"
        fabric._poll_task.assert_called_once()
        print("✓ Create container (async) works")

    def test_create_vm(self):
        """Test creating a virtual machine."""
        print("Testing create_vm...")

        fabric = self.create_mock_client()

        # Mock VM creation response
        upid = "UPID:pve-node1:00000d79:0000000000000004:1636391235:qemu:200:root"
        fabric.client.post = Mock(return_value={"data": upid})
        fabric._poll_task = Mock(return_value={"status": "stopped", "exitstatus": "OK"})
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "stopped",
                "name": "test-vm",
                "maxmem": 4294967296,  # 4GB in bytes
                "uptime": 0,
            }
        })

        request = CreateVMRequest(
            node_id="pve-node1",
            hostname="test-vm",
            memory_mb=4096,
            cores=4,
            storage_gb=100,
        )

        result = fabric.create_vm(request)

        assert result.provider_ref == "qemu:pve-node1:200"
        assert result.kind == InstanceKind.VM
        print("✓ Create VM works")

    def test_start_instance(self):
        """Test starting an instance."""
        print("Testing start_instance...")

        fabric = self.create_mock_client()

        # Mock start response
        fabric.client.post = Mock(return_value={"data": ""})
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "running",
                "hostname": "test-container",
                "maxmem": 2147483648,
                "uptime": 3600,
            }
        })

        provider_ref = "lxc:pve-node1:100"
        result = fabric.start_instance(provider_ref)

        assert result.status == InstanceStatus.RUNNING
        assert result.uptime_seconds == 3600
        print("✓ Start instance works")

    def test_stop_instance(self):
        """Test stopping an instance."""
        print("Testing stop_instance...")

        fabric = self.create_mock_client()

        fabric.client.post = Mock(return_value={"data": ""})
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "stopped",
                "hostname": "test-container",
                "maxmem": 2147483648,
                "uptime": 0,
            }
        })

        provider_ref = "lxc:pve-node1:100"
        result = fabric.stop_instance(provider_ref)

        assert result.status == InstanceStatus.STOPPED
        print("✓ Stop instance works")

    def test_reboot_instance(self):
        """Test rebooting an instance."""
        print("Testing reboot_instance...")

        fabric = self.create_mock_client()

        upid = "UPID:pve-node1:00000d80:0000000000000005:1636391236:lxc:100:root"
        fabric.client.post = Mock(return_value={"data": upid})
        fabric._poll_task = Mock(return_value={"status": "stopped", "exitstatus": "OK"})
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "running",
                "hostname": "test-container",
                "maxmem": 2147483648,
                "uptime": 10,
            }
        })

        provider_ref = "lxc:pve-node1:100"
        result = fabric.reboot_instance(provider_ref)

        assert result.status == InstanceStatus.RUNNING
        fabric._poll_task.assert_called_once()
        print("✓ Reboot instance works")

    def test_delete_instance(self):
        """Test deleting an instance."""
        print("Testing delete_instance...")

        fabric = self.create_mock_client()

        upid = "UPID:pve-node1:00000d81:0000000000000006:1636391237:lxc:100:root"
        fabric.client.delete = Mock(return_value={"data": upid})
        fabric._poll_task = Mock(return_value={"status": "stopped", "exitstatus": "OK"})

        provider_ref = "lxc:pve-node1:100"
        fabric.delete_instance(provider_ref)

        fabric.client.delete.assert_called_once()
        fabric._poll_task.assert_called_once()
        print("✓ Delete instance works")

    def test_get_instance_status(self):
        """Test querying instance status."""
        print("Testing get_instance_status...")

        fabric = self.create_mock_client()

        fabric.client.get = Mock(return_value={
            "data": {
                "status": "running",
                "hostname": "test-container",
                "maxmem": 2147483648,
                "cpus": 2,
                "maxdisk": 53687091200,  # 50GB in bytes
                "uptime": 7200,
            }
        })

        provider_ref = "lxc:pve-node1:100"
        result = fabric.get_instance_status(provider_ref)

        assert result.status == InstanceStatus.RUNNING
        assert result.hostname == "test-container"
        assert result.cores == 2
        assert result.memory_mb == 2048
        assert result.disk_gb == 50
        print("✓ Get instance status works")

    def test_clone_template(self):
        """Test cloning a template."""
        print("Testing clone_template...")

        fabric = self.create_mock_client()

        upid = "UPID:pve-node1:00000d82:0000000000000007:1636391238:lxc:101:root"
        fabric.client.post = Mock(return_value={"data": upid})
        fabric._poll_task = Mock(return_value={"status": "stopped", "exitstatus": "OK"})

        result = fabric.clone_template(
            node_id="pve-node1",
            template_id="lxc:pve-node1:1000",
            new_name="cloned-container",
        )

        assert result == "lxc:pve-node1:101"
        fabric._poll_task.assert_called_once()
        print("✓ Clone template works")

    def test_get_task_status(self):
        """Test querying task status."""
        print("Testing get_task_status...")

        fabric = self.create_mock_client()

        upid = "UPID:pve-node1:00000d78:0000000000000003:1636391234:lxc:100:root"
        fabric.client.get = Mock(return_value={
            "data": {
                "status": "running",
                "starttime": 1636391234,
                "endtime": None,
            }
        })

        result = fabric.get_task_status(upid)

        assert result.status == "running"
        assert result.task_id == upid
        print("✓ Get task status works")

    def test_instance_not_found(self):
        """Test InstanceNotFound exception."""
        print("Testing InstanceNotFound exception...")

        fabric = self.create_mock_client()

        # Try to get status of non-existent instance
        try:
            fabric.get_instance_status("invalid:provider:ref")
            assert False, "Should have raised ValueError"
        except InstanceNotFound:
            print("✓ InstanceNotFound exception works")

    def test_parse_provider_ref(self):
        """Test provider reference parsing."""
        print("Testing provider ref parsing...")

        fabric = self.create_mock_client()

        # Test container ref
        kind, node, vmid = fabric._parse_provider_ref("lxc:node1:100")
        assert kind == "lxc"
        assert node == "node1"
        assert vmid == "100"

        # Test VM ref
        kind, node, vmid = fabric._parse_provider_ref("qemu:node2:200")
        assert kind == "qemu"
        assert node == "node2"
        assert vmid == "200"

        print("✓ Provider ref parsing works")

    def test_build_provider_ref(self):
        """Test provider reference building."""
        print("Testing provider ref building...")

        fabric = self.create_mock_client()

        # Build container ref
        ref = fabric._build_provider_ref(InstanceKind.CONTAINER, "node1", "100")
        assert ref == "lxc:node1:100"

        # Build VM ref
        ref = fabric._build_provider_ref(InstanceKind.VM, "node2", "200")
        assert ref == "qemu:node2:200"

        print("✓ Provider ref building works")

    def test_parse_upid(self):
        """Test UPID parsing."""
        print("Testing UPID parsing...")

        fabric = self.create_mock_client()

        upid = "UPID:pve-node1:00000d78:0000000000000003:1636391234:lxc:100:root"
        node, parsed_upid = fabric._parse_upid(upid)

        assert node == "pve-node1"
        assert parsed_upid == upid

        print("✓ UPID parsing works")


def run_all_integration_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("Fabric Integration Tests")
    print("=" * 60)

    test_suite = TestProxmoxFabricIntegration()

    tests = [
        test_suite.test_create_container_sync_response,
        test_suite.test_create_container_async_response,
        test_suite.test_create_vm,
        test_suite.test_start_instance,
        test_suite.test_stop_instance,
        test_suite.test_reboot_instance,
        test_suite.test_delete_instance,
        test_suite.test_get_instance_status,
        test_suite.test_clone_template,
        test_suite.test_get_task_status,
        test_suite.test_instance_not_found,
        test_suite.test_parse_provider_ref,
        test_suite.test_build_provider_ref,
        test_suite.test_parse_upid,
    ]

    results = []
    print("\n")
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if all(results):
        print("✓ All integration tests passed!")
        return 0
    else:
        print("✗ Some integration tests failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_integration_tests()
    sys.exit(exit_code)
