# CargoPulse Authorization Matrix & RBAC Architecture

This document defines the Role-Based Access Control (RBAC), multi-tenant isolation model, permission hierarchy, and security safeguards implemented in CargoPulse.

---

## 1. Multi-Tenant Architecture & Data Isolation

CargoPulse enforces strict tenant boundaries at the database and application levels:
1. **Tenant Boundary**: Every business entity (shipments, bookings, vehicles, drivers, users) belongs to an `organization_id`.
2. **Server-Side Enforcement**: All database queries and operations require `WHERE organization_id = :current_user_org_id`.
3. **IDOR Prevention**: Any attempt by a user from Organization A to view, modify, or delete a resource belonging to Organization B returns `404 Not Found` (or `403 Forbidden`). Organization IDs are never trusted from client payloads for authorization scoping.
4. **Master Transporter Sharing**: Transporters (carriers) have master profiles. Multiple manufacturer organizations associate with a single carrier via `organization_transporters`. This allows a carrier to service multiple manufacturers without duplicating carrier profiles, vehicles, or drivers, while maintaining strict isolation of shipment, booking, and rate data.

---

## 2. Standard User Roles

| Role Name | System Code | Scope | Primary Responsibility |
|:---|:---|:---|:---|
| **Super Admin** | `SUPER_ADMIN` | Global | Platform operator with wildcard (`*:*`) access across system settings and all tenants. |
| **Organization Admin** | `ORGANIZATION_ADMIN` | Tenant | Full administrative control over tenant profile, user lifecycle, roles, transporter partnerships, and operational modules. |
| **Dispatch Manager** | `DISPATCH_MANAGER` | Tenant | Creates and edits freight shipments, runs transporter matching, issues dispatch bookings, and manages pickup commitments. |
| **Operations Manager** | `OPERATIONS_MANAGER` | Tenant | Monitors shipment execution, tracks pickup SLA commitments, handles exceptions, approves recovery actions, and verifies PODs. |
| **Transporter Admin** | `TRANSPORTER_ADMIN` | Carrier Tenant | Manages carrier profile, fleet vehicles, drivers, responds to booking requests, and submits milestone telemetry. |
| **Driver** | `DRIVER` | Carrier / Assigned | Executes assigned shipments, records facility arrivals, confirms pickups, submits delivery progress, and uploads physical POD evidence. |

---

## 3. Granular Permission Catalog

| Permission Code | Module | Display Name | Description |
|:---|:---|:---|:---|
| `organization:read` | Organization | View Organization Profile | Access company profile, slug, and basic configuration |
| `organization:manage` | Organization | Manage Organization | Update company profile, billing email, tax identifier |
| `organization:settings` | Organization | Manage Settings | Modify operational thresholds, SLA timers, and custom settings |
| `users:read` | Users | View Organization Users | View user roster and profiles within organization |
| `users:manage` | Users | Manage Organization Users | Invite, update roles, activate/deactivate, and revoke users |
| `roles:read` | Roles | View Roles & Permissions | View available role definitions and permission catalogs |
| `shipments:read` | Shipments | View Shipments | View shipment list and details within tenant |
| `shipments:create` | Shipments | Create Shipments | Create new outbound freight shipments |
| `shipments:update` | Shipments | Update Shipments | Edit draft and pending shipments |
| `shipments:manage` | Shipments | Full Shipment Management | Full control to modify, reassign, or cancel shipments |
| `shipment_history:read` | Shipments | View Shipment History | Inspect immutable shipment event audit log |
| `assigned_shipments:read`| Shipments | View Assigned Shipments | Driver-only: view only shipments assigned to current driver |
| `transporters:read` | Transporters | View Transporters | View carrier directory and linked transporters |
| `transporters:manage` | Transporters | Manage Transporters | Link, unlink, and configure carrier partnerships |
| `transporters:match` | Transporters | Match Transporters | Run carrier matching engine and evaluate rank scores |
| `transporter_profile:read` | Transporters | View Carrier Profile | View carrier profile and compliance details |
| `transporter_profile:manage`| Transporters | Manage Carrier Profile | Update carrier details and compliance records |
| `fleet:read` | Fleet | View Fleet | View carrier vehicles and driver roster |
| `fleet:manage` | Fleet | Manage Fleet | Register and manage fleet vehicles and drivers |
| `bookings:create` | Dispatch | Create Bookings | Dispatch shipment booking requests to carriers |
| `bookings:read` | Dispatch | View Bookings | View booking requests and status |
| `bookings:respond` | Dispatch | Accept/Reject Bookings | Carrier response to booking requests |
| `commitments:manage` | Dispatch | Manage Commitments | Confirm pickup commitment windows and driver assignments |
| `commitments:read` | Dispatch | Monitor Pickups | Monitor pickup execution against committed SLA |
| `shipment_arrival:record` | Execution | Record Arrival | Driver logs arrival at pickup facility |
| `shipment_pickup:confirm` | Execution | Confirm Pickup | Driver confirms loading departure |
| `shipment_delivery:submit` | Execution | Submit Delivery | Driver logs delivery arrival and unloading |
| `milestones:submit` | Execution | Submit Milestones | Submit en-route milestone telemetry |
| `pod:upload` | Execution | Upload POD Evidence | Upload physical proof of delivery documents and photos |
| `pod:verify` | Operations | Verify Proof of Delivery | Review and approve/reject signed PODs |
| `pod:read` | Operations | View Proof of Delivery | View uploaded POD documents and signatures |
| `exceptions:manage` | Operations | Manage Exceptions | Log, escalate, and resolve shipment exceptions |
| `exceptions:read` | Operations | View Exceptions | View incident tickets and exception records |
| `recovery:manage` | Operations | Manage Recovery | Initiate and approve emergency recovery actions |
| `reconciliation:manage` | Operations | Manage Reconciliation | Resolve delivery discrepancies and billing disputes |
| `analytics:read` | Analytics | View Analytics | Access operational analytics, KPIs, and dashboards |
| `audit:read` | Audit | View Audit Trail | Inspect immutable platform compliance audit logs |
| `admin:all` | Admin | Full Organization Admin | Tenant-level wildcard administrator privileges |

---

## 4. Role-to-Permission Mapping Matrix

| Permission Code | Super Admin | Organization Admin | Dispatch Manager | Operations Manager | Transporter Admin | Driver |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `*:*` (Wildcard) | **YES** | NO | NO | NO | NO | NO |
| `admin:all` | **YES** | **YES** | NO | NO | NO | NO |
| `organization:read` | **YES** | **YES** | **YES** | **YES** | **YES** | NO |
| `organization:manage` | **YES** | **YES** | NO | NO | NO | NO |
| `organization:settings` | **YES** | **YES** | NO | NO | NO | NO |
| `users:read` | **YES** | **YES** | NO | NO | NO | NO |
| `users:manage` | **YES** | **YES** | NO | NO | NO | NO |
| `roles:read` | **YES** | **YES** | NO | NO | NO | NO |
| `shipments:read` | **YES** | **YES** | **YES** | **YES** | NO | NO |
| `shipments:create` | **YES** | **YES** | **YES** | NO | NO | NO |
| `shipments:update` | **YES** | **YES** | **YES** | NO | NO | NO |
| `shipments:manage` | **YES** | **YES** | NO | NO | NO | NO |
| `shipment_history:read` | **YES** | **YES** | **YES** | **YES** | NO | NO |
| `assigned_shipments:read` | **YES** | NO | NO | NO | NO | **YES** |
| `transporters:read` | **YES** | **YES** | **YES** | NO | NO | NO |
| `transporters:manage` | **YES** | **YES** | NO | NO | NO | NO |
| `transporters:match` | **YES** | **YES** | **YES** | NO | NO | NO |
| `transporter_profile:read` | **YES** | NO | NO | NO | **YES** | NO |
| `transporter_profile:manage`| **YES** | NO | NO | NO | **YES** | NO |
| `fleet:read` | **YES** | NO | NO | NO | **YES** | NO |
| `fleet:manage` | **YES** | NO | NO | NO | **YES** | NO |
| `bookings:create` | **YES** | **YES** | **YES** | NO | NO | NO |
| `bookings:read` | **YES** | **YES** | **YES** | NO | **YES** | NO |
| `bookings:respond` | **YES** | NO | NO | NO | **YES** | NO |
| `commitments:manage` | **YES** | **YES** | **YES** | NO | NO | NO |
| `commitments:read` | **YES** | **YES** | **YES** | **YES** | NO | NO |
| `shipment_arrival:record` | **YES** | NO | NO | NO | NO | **YES** |
| `shipment_pickup:confirm` | **YES** | NO | NO | NO | NO | **YES** |
| `shipment_delivery:submit`| **YES** | NO | NO | NO | NO | **YES** |
| `milestones:submit` | **YES** | NO | NO | NO | **YES** | NO |
| `pod:upload` | **YES** | NO | NO | NO | NO | **YES** |
| `pod:verify` | **YES** | **YES** | NO | **YES** | NO | NO |
| `pod:read` | **YES** | **YES** | **YES** | **YES** | **YES** | NO |
| `exceptions:manage` | **YES** | **YES** | NO | **YES** | NO | NO |
| `exceptions:read` | **YES** | **YES** | NO | **YES** | NO | NO |
| `recovery:manage` | **YES** | **YES** | NO | **YES** | NO | NO |
| `reconciliation:manage`| **YES** | **YES** | NO | **YES** | NO | NO |
| `analytics:read` | **YES** | **YES** | NO | **YES** | NO | NO |
| `audit:read` | **YES** | **YES** | NO | NO | NO | NO |

---

## 5. API Endpoint Authorization Mapping

| HTTP Method | API Path | Required Permission | Description |
|:---|:---|:---|:---|
| `GET` | `/api/v1/organizations/me` | `organization:read` | Get caller's organization profile |
| `PUT` | `/api/v1/organizations/me` | `organization:manage` | Update caller's organization profile |
| `GET` | `/api/v1/organizations/me/settings` | `organization:read` | Get organization operational settings |
| `PATCH` | `/api/v1/organizations/me/settings` | `organization:manage` | Update organization operational settings |
| `GET` | `/api/v1/organizations/me/roles` | `roles:read` | List available tenant and system roles |
| `GET` | `/api/v1/organizations/me/permissions` | `roles:read` | List all platform permissions |
| `GET` | `/api/v1/organizations/me/users` | `users:read` | List all users in organization |
| `POST` | `/api/v1/organizations/me/users` | `users:manage` | Invite / create user in organization |
| `GET` | `/api/v1/organizations/me/users/{id}` | `users:read` | Get user details (tenant-scoped) |
| `PUT` | `/api/v1/organizations/me/users/{id}/roles`| `users:manage` | Update assigned roles for user |
| `PATCH` | `/api/v1/organizations/me/users/{id}/status`| `users:manage` | Activate / deactivate user account |
| `DELETE`| `/api/v1/organizations/me/users/{id}` | `users:manage` | Permanently revoke user access |
| `GET` | `/api/v1/organizations/me/transporters` | `transporters:read` | List linked transporters |
| `POST` | `/api/v1/organizations/me/transporters/link`| `transporters:manage` | Link existing transporter to tenant |
| `DELETE`| `/api/v1/organizations/me/transporters/{id}`| `transporters:manage` | Unlink transporter from tenant |

---

## 6. Security & Anti-Escalation Controls

1. **Privilege Escalation Prevention**:
   - Only global `is_superadmin` users can assign the `SUPER_ADMIN` role or set `is_superadmin = true`.
   - Tenant administrators cannot assign roles belonging to other organizations or roles with permissions beyond their tenant scope.
2. **Immediate Session Revocation**:
   - When a user's account is deactivated (`PATCH /status` with `is_active=false`) or revoked (`DELETE`), all active refresh sessions in `refresh_sessions` are instantly set to `is_revoked = true` with `revoked_at = NOW()`.
   - Any refresh token presented from that session will be rejected immediately, terminating access before token expiration.
3. **Self-Tampering Prevention**:
   - An administrator cannot deactivate or revoke their own account (`HTTP 400 Bad Request`).
4. **Cross-Tenant IDOR Immunity**:
   - Even if an attacker guesses or steals a valid UUID for a user, shipment, or setting from another organization, all queries filter on `organization_id == current_user.organization_id`. The server responds with `404 Not Found`, denying existence of other tenants' records.
