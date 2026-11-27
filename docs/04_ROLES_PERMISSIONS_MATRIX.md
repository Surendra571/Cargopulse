# 04. Roles & Permissions Matrix

This document defines the Role-Based Access Control (RBAC) architecture, tenant hierarchy, and the granular permission matrix across all platform capabilities in CargoPulse.

---

## 1. Organization & Tenant Taxonomy

CargoPulse supports three primary organization types:
1. **Shipper Tenant (`SHIPPER`)**: Manufacturing plants, FMCG brand owners, chemical/automotive industrial producers.
2. **Transporter Tenant (`TRANSPORTER`)**: Dedicated fleet carriers, 3PL logistics service providers, brokerage partners.
3. **Platform Provider (`PLATFORM`)**: CargoPulse SaaS system operations and support.

Each user belongs to an Organization Tenant and is assigned one or more Roles. In addition, users can be assigned a **Facility Scope** (e.g., restricted to specific manufacturing plants or loading docks).

---

## 2. Platform Standard Roles

### Shipper Organization Roles
- **`SHIPPER_ADMIN`**: Complete administrative control over the shipper's organization, plants, user management, billing, and integrations.
- **`LOGISTICS_MANAGER`**: Operational supervisory role; creates freight contracts, manages carrier panels, approves reconciliation discrepancies, monitors overall network OTIF.
- **`DISPATCHER`**: Frontline operational planner; creates shipments, initiates bookings, monitors pickup SLAs, handles real-time exceptions and recovery dispatch.
- **`GATE_SECURITY_OFFICER`**: Plant gatekeeper; validates driver credentials, performs two-factor OTP gate check-in, records tare/gross weights, tracks vehicle dock entry/exit.
- **`FINANCE_AUDITOR`**: Audits completed shipments, reviews detention/demurrage charges, verifies POD compliance, approves carrier freight invoices.
- **`SHIPPER_VIEWER`**: Read-only access across shipments, tracking, and reports.

### Transporter Organization Roles
- **`CARRIER_ADMIN`**: Manages carrier profile, vehicle fleet, driver roster, rate cards, and transporter user accounts.
- **`CARRIER_DISPATCHER`**: Reviews incoming load tenders, accepts/rejects bookings, nominates vehicles and drivers, monitors trip progress, reports transit exceptions.
- **`DRIVER`**: Mobile web/app access; receives trip assignments, completes gate-in OTP authentication, updates transit status, and uploads digital e-PODs.
- **`CARRIER_BILLING`**: Submits freight invoices, reviews detention claims, tracks payment voucher approvals.

### Platform Super Roles
- **`PLATFORM_SUPERADMIN`**: Full platform oversight across all tenants, global configurations, and infrastructure monitoring.
- **`PLATFORM_SUPPORT`**: Read-only cross-tenant diagnostics and customer support impersonation with strict time-bounded audit logging.

---

## 3. Granular Permission Definitions

Permissions follow the format: `<module>:<resource>:<action>`

| Permission Code | Description |
|---|---|
| `org:manage` | Manage company profile, plants, settings, and integrations |
| `users:manage` | Invite, update, and deactivate organization users |
| `rbac:assign` | Assign roles and facility scopes to users |
| `shipments:create` | Create new shipment orders (manual or bulk) |
| `shipments:read` | View shipment orders and cargo specifications |
| `shipments:update` | Edit shipment details prior to dispatch |
| `shipments:cancel` | Cancel an active shipment |
| `transporters:manage`| Add, verify, or suspend transporter vendors |
| `rate_cards:manage` | Configure contracted rate cards and detention rules |
| `rate_cards:read` | View contracted freight rates |
| `fleet:manage` | Register, update, and verify vehicles and drivers |
| `fleet:read` | View vehicle and driver lists |
| `matching:execute` | Trigger matching algorithms (waterfall, bidding, pro-rata) |
| `bookings:tender` | Issue booking tenders to transporters |
| `bookings:respond` | Accept or decline load tenders (Transporter only) |
| `bookings:nominate`| Nominate vehicle and driver for a confirmed booking |
| `pickup:gate_in` | Verify OTP and register vehicle physical gate arrival |
| `pickup:loading` | Record dock berthing, tare weight, loading start/finish |
| `pickup:gate_out` | Issue gate pass and record gross weight & gate exit |
| `pickup:override` | Manually override failed pickup state with justification |
| `tracking:read` | View real-time GPS telematics, ETA, and route maps |
| `tracking:telemetry`| Ingest telematics updates (Driver app, IoT GPS, webhooks)|
| `exceptions:raise` | Log an operational exception (delay, breakdown, refusal) |
| `exceptions:resolve`| Acknowledge, resolve, or transship an active exception |
| `ai:recommend` | View and execute AI coordinator recommendations |
| `pod:upload` | Submit electronic signatures, photos, and delivery notes |
| `pod:verify` | Inspect, approve, or reject submitted Proof of Delivery |
| `reconcile:read` | View billing calculations and three-way match sheets |
| `reconcile:approve` | Approve freight payments and detention claims |
| `reconcile:dispute` | Raise financial dispute against carrier invoice |
| `analytics:read` | View dashboards, OTIF metrics, and transporter scorecards |
| `integrations:manage`| Configure ERP webhooks, API keys, and partner connectors |
| `audit:read` | View immutable audit logs and compliance history |

---

## 4. Roles vs. Permissions Matrix

The following matrix maps default roles to granular permissions.

| Permission Code | `SHIPPER_ADMIN` | `LOGISTICS_MGR` | `DISPATCHER` | `GATE_OFFICER` | `FINANCE_AUDITOR` | `CARRIER_ADMIN` | `CARRIER_DISP` | `DRIVER` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `org:manage` | ✅ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ |
| `users:manage` | ✅ | ❌ | ❌ | ❌ | ❌ | ✅* | ❌ | ❌ |
| `rbac:assign` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `shipments:create` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `shipments:read` | ✅ | ✅ | ✅ | ✅ (assigned) | ✅ | ✅ (assigned) | ✅ (assigned) | ✅ (trip) |
| `shipments:update` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `shipments:cancel` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `transporters:manage`| ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `rate_cards:manage`| ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `rate_cards:read` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅* | ❌ | ❌ |
| `fleet:manage` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `fleet:read` | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| `matching:execute` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `bookings:tender` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `bookings:respond` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `bookings:nominate`| ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `pickup:gate_in` | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `pickup:loading` | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `pickup:gate_out` | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `pickup:override` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `tracking:read` | ✅ | ✅ | ✅ | ✅ (assigned) | ❌ | ✅ | ✅ | ✅ (trip) |
| `tracking:telemetry`| ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `exceptions:raise` | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| `exceptions:resolve`| ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ai:recommend` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `pod:upload` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `pod:verify` | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `reconcile:read` | ✅ | ✅ | ❌ | ❌ | ✅ | ✅* | ❌ | ❌ |
| `reconcile:approve`| ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `reconcile:dispute`| ✅ | ✅ | ❌ | ❌ | ✅ | ✅* | ❌ | ❌ |
| `analytics:read` | ✅ | ✅ | ✅ | ❌ | ✅ | ✅* | ❌ | ❌ |
| `integrations:manage`| ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `audit:read` | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |

*\*Applies exclusively to the Transporter's own organization scope.*

---

## 5. Server-Side Enforcement Pattern

Authorization is enforced declaratively in FastAPI route dependencies:

```python
@router.post(
    "/shipments/{shipment_id}/cancel",
    dependencies=[
        Depends(require_permission("shipments:cancel")),
        Depends(require_tenant_context())
    ]
)
async def cancel_shipment(
    shipment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ShipmentService = Depends(get_shipment_service)
):
    ...
```

1. **Authentication Guard**: Verifies JWT cryptographic signature, expiry, and revocation state in Redis.
2. **Tenant Boundary Guard**: Injects verified `tenant_id` from claims; guarantees zero cross-tenant contamination.
3. **RBAC Guard**: Evaluates effective permissions computed from the user's role assignments.
4. **Object-Level Guard**: Verifies that the specific entity being manipulated belongs to the active tenant (or has an authorized cross-tenant booking relationship).
