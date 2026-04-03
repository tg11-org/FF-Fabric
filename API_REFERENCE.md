# Fabric API Reference

Fabric is the infrastructure abstraction API consumed by Pulse. It supports VM/container provisioning and lifecycle operations.

## Local Base URL

- `http://localhost:8002`

## Interactive Docs (FastAPI)

- Swagger UI: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`
- OpenAPI JSON: `http://localhost:8002/openapi.json`

## Endpoints

- `GET /health`
  - Health check

### Provisioning

- `POST /vms`
  - Create VM
- `POST /containers`
  - Create container

### Lifecycle

- `POST /instances/{provider_ref}/start`
- `POST /instances/{provider_ref}/stop`
- `POST /instances/{provider_ref}/reboot`
- `DELETE /instances/{provider_ref}`
- `GET /instances/{provider_ref}/status`

## Runtime Mode Notes

- Fake mode (local dev): set `FABRIC_PROVIDER=fake`
- Proxmox mode: set `FABRIC_PROVIDER=proxmox` plus `PROXMOX_URL` and `PROXMOX_API_TOKEN`
