"""HTTP API contract tests for Fabric endpoints used by Pulse."""

from datetime import datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient

from fabric.api import app
from fabric.models import CreateInstanceResult, InstanceKind, InstanceStatus, InstanceStatusResult


def _mock_provider():
    provider = Mock()
    provider.create_container.return_value = CreateInstanceResult(
        provider_ref="lxc:node-1:101",
        node_id="node-1",
        kind=InstanceKind.CONTAINER,
        status=InstanceStatus.RUNNING,
        created_at=datetime.utcnow(),
    )
    provider.create_vm.return_value = CreateInstanceResult(
        provider_ref="qemu:node-1:201",
        node_id="node-1",
        kind=InstanceKind.VM,
        status=InstanceStatus.RUNNING,
        created_at=datetime.utcnow(),
    )
    provider.start_instance.return_value = InstanceStatusResult(
        provider_ref="qemu:node-1:201",
        node_id="node-1",
        kind=InstanceKind.VM,
        status=InstanceStatus.RUNNING,
    )
    provider.stop_instance.return_value = InstanceStatusResult(
        provider_ref="qemu:node-1:201",
        node_id="node-1",
        kind=InstanceKind.VM,
        status=InstanceStatus.STOPPED,
    )
    provider.reboot_instance.return_value = InstanceStatusResult(
        provider_ref="qemu:node-1:201",
        node_id="node-1",
        kind=InstanceKind.VM,
        status=InstanceStatus.RUNNING,
    )
    provider.get_instance_status.return_value = InstanceStatusResult(
        provider_ref="qemu:node-1:201",
        node_id="node-1",
        kind=InstanceKind.VM,
        status=InstanceStatus.RUNNING,
    )
    return provider


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_container_contract(monkeypatch):
    provider = _mock_provider()
    monkeypatch.setattr("fabric.api.get_provider", lambda: provider)

    client = TestClient(app)
    response = client.post(
        "/containers",
        json={
            "node_id": "node-1",
            "hostname": "ct-1",
            "vcpu": 2,
            "ram_mb": 2048,
            "disk_gb": 20,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider_ref"] == "lxc:node-1:101"
    assert body["status"] == "running"


def test_create_vm_contract(monkeypatch):
    provider = _mock_provider()
    monkeypatch.setattr("fabric.api.get_provider", lambda: provider)

    client = TestClient(app)
    response = client.post(
        "/vms",
        json={
            "node_id": "node-1",
            "hostname": "vm-1",
            "vcpu": 4,
            "ram_mb": 4096,
            "disk_gb": 40,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider_ref"] == "qemu:node-1:201"
    assert body["status"] == "running"


def test_lifecycle_endpoints(monkeypatch):
    provider = _mock_provider()
    monkeypatch.setattr("fabric.api.get_provider", lambda: provider)

    client = TestClient(app)

    start_resp = client.post("/instances/qemu:node-1:201/start", json={"node_id": "node-1"})
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "running"

    stop_resp = client.post("/instances/qemu:node-1:201/stop", json={"node_id": "node-1"})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"

    reboot_resp = client.post("/instances/qemu:node-1:201/reboot", json={"node_id": "node-1"})
    assert reboot_resp.status_code == 200
    assert reboot_resp.json()["status"] == "running"

    delete_resp = client.request("DELETE", "/instances/qemu:node-1:201", json={"node_id": "node-1"})
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "deleted"


def test_status_endpoint(monkeypatch):
    provider = _mock_provider()
    monkeypatch.setattr("fabric.api.get_provider", lambda: provider)

    client = TestClient(app)
    response = client.get("/instances/qemu:node-1:201/status", params={"node_id": "node-1"})

    assert response.status_code == 200
    assert response.json()["status"] == "running"
