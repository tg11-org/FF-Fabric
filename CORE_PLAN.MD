## 1. Full platform layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│                                Users                                 │
│   Customers / Admins / Support / Investors (read-only dashboards)    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                               Forge                                  │
│                    Frontend / Dashboard / UI Layer                   │
│                                                                      │
│  - Login / auth UI                                                   │
│  - Customer server list                                              │
│  - Create / stop / reboot / destroy buttons                          │
│  - Billing pages                                                     │
│  - Admin views                                                       │
│  - Monitoring / usage charts                                         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTPS / JSON API
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                                Core                                  │
│                    API / Control Plane / Main Brain                  │
│                                                                      │
│  - Auth / sessions / permissions                                     │
│  - Plan definitions                                                  │
│  - Ownership checks                                                  │
│  - Node selection logic                                              │
│  - Capacity checks                                                   │
│  - Billing state checks                                              │
│  - Job creation                                                      │
│  - Audit logging                                                     │
│  - Public API for Forge                                              │
└───────────────┬───────────────────────┬──────────────────────────────┘
                │                       │
                │ reads/writes          │ pushes jobs
                ▼                       ▼
┌─────────────────────────────┐   ┌────────────────────────────────────┐
│        Core Database        │   │         Queue / Broker             │
│         PostgreSQL          │   │       Redis / RabbitMQ             │
│                             │   │                                    │
│  Tables like:               │   │  Queues like:                      │
│  - users                    │   │  - provision_instance              │
│  - orgs/accounts            │   │  - start_instance                  │
│  - plans                    │   │  - stop_instance                   │
│  - nodes                    │   │  - destroy_instance                │
│  - instances                │   │  - resize_instance                 │
│  - volumes                  │   │  - sync_status                     │
│  - IP allocations           │   │  - backup_now                      │
│  - jobs/tasks               │   │                                    │
│  - billing records          │   └────────────────────────────────────┘
│  - audit log                │
└─────────────────────────────┘
                                                ▲
                                                │ consumes jobs / updates results
                                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                               Pulse                                  │
│                   Worker / Executor / Async Engine                   │
│                                                                      │
│  - Picks up queued jobs                                              │
│  - Calls Fabric methods                                              │
│  - Polls Proxmox task status                                         │
│  - Updates Core DB with results                                      │
│  - Retries failed jobs                                               │
│  - Sends events / notifications                                      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ provider calls
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                               Fabric                                 │
│               Infrastructure Abstraction / Proxmox Adapter           │
│                                                                      │
│  - create_vm()                                                       │
│  - create_container()                                                │
│  - clone_template()                                                  │
│  - start_instance()                                                  │
│  - stop_instance()                                                   │
│  - delete_instance()                                                 │
│  - resize_disk()                                                     │
│  - get_console_ticket()                                              │
│  - query_node_capacity()                                             │
│                                                                      │
│  Internally speaks:                                                  │
│  - Proxmox REST API                                                  │
│  - maybe pvesh/qm/pct later for ops tooling                          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                              Proxmox                                 │
│                    Hypervisor / Compute Infrastructure               │
│                                                                      │
│  - Nodes                                                             │
│  - VMs                                                               │
│  - LXC containers                                                    │
│  - Storage pools                                                     │
│  - Networks / bridges                                                │
│  - Snapshots / backups                                               │
│  - Console access                                                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Customer Instances                           │
│                                                                      │
│  - VPS containers                                                    │
│  - Full VMs                                                          │
│  - VPN nodes                                                         │
│  - Storage nodes                                                     │
│  - Internal TG11 services                                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data ownership model

This part matters a lot.

```text
Forge   = presentation layer
Core    = source of truth for business state
Pulse   = executor of requested work
Fabric  = infra translation layer
Proxmox = source of truth for actual hypervisor state
```

In practice:

```text
Core knows:
- who owns what
- which plan an instance is on
- billing status
- which node was assigned
- which IP should belong to it
- job history
- audit history

Proxmox knows:
- VMID / CTID
- CPU / RAM / disk actually configured
- whether instance is running
- snapshots / backups
- storage location
```

So Core is your **business truth**, Proxmox is your **infra truth**.

---

## 3. Suggested databases / state stores

### Core Database: PostgreSQL

Use this for durable platform state.

```text
users
accounts
organizations
plans
plan_features
nodes
node_capacity_snapshots
instances
instance_networks
instance_disks
instance_credentials_metadata
ip_allocations
jobs
job_attempts
billing_subscriptions
billing_invoices
audit_events
support_events
```

### Queue / Broker: Redis or RabbitMQ

Use this for async job handling.

```text
provision jobs
lifecycle jobs
sync jobs
billing-triggered suspension jobs
backup jobs
cleanup jobs
```

### Optional Metrics DB later

For graphs and monitoring later, maybe:

```text
Prometheus / VictoriaMetrics / Influx
```

For now, not required.

---

## 4. Main flow: customer creates a server

```text
[User in Forge]
    │
    │ clicks "Create Server"
    ▼
[Forge]
    │
    │ POST /instances
    ▼
[Core]
    │
    ├─ validate logged-in user
    ├─ validate billing/account state
    ├─ validate selected plan
    ├─ validate quotas / limits
    ├─ choose target node
    ├─ reserve capacity in DB
    ├─ create instance record (status = provisioning)
    ├─ create job record
    └─ enqueue job: provision_instance
    ▼
[Queue]
    │
    ▼
[Pulse]
    │
    ├─ load job
    ├─ load instance + plan + node details from Core DB
    ├─ call Fabric.clone_template(...) or create_container(...)
    ▼
[Fabric]
    │
    ├─ call Proxmox API
    ├─ create VM/CT
    ├─ set CPU / RAM / disk / network
    ├─ attach cloud-init or config
    ├─ start instance
    └─ return VMID/CTID + task refs
    ▼
[Pulse]
    │
    ├─ poll task completion
    ├─ update instance status in Core DB
    ├─ store VMID / IP / node / timestamps
    └─ mark job complete
    ▼
[Core DB]
    │
    ▼
[Forge]
    │
    └─ displays: "Instance Ready"
```

---

## 5. Main flow: start / stop / reboot

```text
[User clicks Reboot]
    ▼
[Forge]
    ▼
[Core]
    ├─ confirm ownership
    ├─ create lifecycle job
    └─ enqueue
    ▼
[Pulse]
    ├─ call Fabric.reboot_instance(instance_id)
    ├─ poll task
    └─ update DB
    ▼
[Core DB]
    ▼
[Forge shows updated state]
```

---

## 6. Main flow: destroy instance

```text
[User clicks Destroy]
    ▼
[Forge]
    ▼
[Core]
    ├─ verify confirmation
    ├─ verify ownership / permission
    ├─ mark instance status = deleting
    ├─ create destroy job
    └─ enqueue
    ▼
[Pulse]
    ├─ call Fabric.stop_instance()
    ├─ call Fabric.delete_instance()
    ├─ release IP allocation
    ├─ release reserved capacity
    └─ mark instance deleted in Core DB
    ▼
[Forge]
    └─ instance disappears from active list
```

---

## 7. Main flow: periodic state sync

You want this because sometimes Proxmox and Core can drift.

```text
[Scheduler / cron]
    ▼
[Pulse]
    ├─ query all active nodes via Fabric
    ├─ fetch instance states from Proxmox
    ├─ compare with Core DB
    ├─ repair mismatches
    └─ store status snapshots
```

Example mismatches:

```text
Core says running, Proxmox says stopped
Core says IP assigned, Proxmox NIC missing
Core says VM exists, Proxmox no longer has VM
```

This sync job is very important in production.

---

## 8. Main flow: billing-triggered suspension

```text
[Billing system / invoice overdue]
    ▼
[Core]
    ├─ mark account overdue
    ├─ select affected instances
    ├─ create suspend jobs
    └─ enqueue
    ▼
[Pulse]
    ├─ call Fabric.stop_instance()
    └─ update instance state = suspended
    ▼
[Forge]
    └─ shows "Suspended: payment required"
```

Later you could also do:

```text
overdue > 7 days → stop
overdue > 30 days → delete after backup
```

---

## 9. Main flow: console access

This one is important because you do **not** want Forge talking to raw Proxmox directly without mediation.

```text
[User clicks Console]
    ▼
[Forge]
    ▼
[Core]
    ├─ verify ownership
    ├─ request console ticket from Fabric
    └─ return short-lived console session details
    ▼
[Fabric]
    └─ gets temporary Proxmox console ticket
    ▼
[Forge]
    └─ opens noVNC / console proxy
```

So the browser only gets a **short-lived session**, not permanent Proxmox credentials.

---

## 10. Suggested DB schema concept

A simple early model could look like this:

```text
accounts
--------
id
name
status
created_at

users
-----
id
account_id
email
password_hash
role
created_at

plans
-----
id
code
name
family          (balanced / hr / hc / vpn / storage)
instance_type   (vm / ct / service)
vcpu
ram_mb
disk_gb
bandwidth_tb
price_monthly
active

nodes
-----
id
name
provider        (fabric/proxmox)
role            (general / highram / highcpu / storage)
status
total_vcpu
total_ram_mb
total_disk_gb
reserved_vcpu
reserved_ram_mb
reserved_disk_gb

instances
---------
id
account_id
plan_id
node_id
kind            (vm / ct / vpn / storage)
provider_ref     (vmid / ctid / service id)
hostname
status
primary_ip
vcpu
ram_mb
disk_gb
created_at
updated_at

instance_networks
-----------------
id
instance_id
ip_address
gateway
cidr
mac_address
is_primary

jobs
----
id
instance_id
type            (provision/start/stop/reboot/delete/resize/sync)
status          (queued/running/succeeded/failed)
payload_json
error_text
created_at
started_at
finished_at

audit_events
------------
id
account_id
user_id
instance_id
action
details_json
created_at

billing_subscriptions
---------------------
id
account_id
plan_id
status
renewal_date
price_monthly
```

---

## 11. Suggested service boundaries

```text
Forge
 └─ only UI + auth/session-facing frontend logic

Core
 ├─ Auth module
 ├─ Plans module
 ├─ Instance API
 ├─ Billing module
 ├─ Audit module
 ├─ Node scheduler
 └─ Queue producer

Pulse
 ├─ Provision worker
 ├─ Lifecycle worker
 ├─ Sync worker
 ├─ Backup worker
 └─ Cleanup worker

Fabric
 ├─ Proxmox adapter
 ├─ Compute methods
 ├─ Storage methods
 ├─ Network methods
 └─ Console ticket methods
```

---

## 12. Production-minded naming map

```text
Forge   = user experience
Core    = business logic and control plane
Pulse   = asynchronous execution engine
Fabric  = infrastructure abstraction layer
Proxmox = current infrastructure implementation under Fabric
```

So later, if you ever add another backend:

```text
Fabric
 ├─ Proxmox provider
 ├─ bare-metal provider
 ├─ maybe cloud provider later
```

Core stays the same.
