# 07. API Module Plan & Specification

The CargoPulse backend is built using **FastAPI** with Python 3.12, strict Pydantic v2 schemas, SQLAlchemy 2.0 Async ORM, and automated OpenAPI documentation.

---

## 1. Global API Standards & Conventions

### 1.1 URI Hierarchy & Versioning
- Standard Base URL: `/api/v1`
- Multi-tenancy Context: Injected via cryptographically verified JWT bearer token; no tenant ID in path parameters unless accessing global platform administrative APIs.
- Resource Naming: RESTful plural nouns (e.g., `/shipments`, `/bookings`, `/facilities`).

### 1.2 Unified Response Envelope
All non-streaming REST endpoints return a deterministic JSON envelope:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2026-11-20T14:39:22Z",
    "request_id": "req_01jcvz81qfe..."
  }
}
```

### 1.3 Paginated Response Envelope
For collections, cursor-based or limit-offset pagination is standardized:

```json
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "total_records": 1240,
    "current_page": 1,
    "page_size": 25,
    "total_pages": 50,
    "has_next": true,
    "has_prev": false
  },
  "meta": {
    "timestamp": "2026-11-20T14:39:22Z",
    "request_id": "req_01jcvz81qfe..."
  }
}
```

### 1.4 Unified Error Envelope
HTTP errors return structured machine-readable error schemas:

```json
{
  "success": false,
  "error": {
    "code": "PICKUP_SLA_BREACHED",
    "message": "Vehicle placement cutoff expired 15 minutes ago.",
    "details": [
      {
        "field": "nomination_cutoff_at",
        "issue": "Transporter failed to nominate vehicle before 14:00 UTC."
      }
    ],
    "trace_id": "trc_98217391823"
  }
}
```

---

## 2. API Endpoints by Module

### Module 1: Authentication & Identity
- `POST /api/v1/auth/register` - Organization and Admin user registration.
- `POST /api/v1/auth/login` - Email/password login; returns JWT access token + refresh token cookie.
- `POST /api/v1/auth/refresh` - Rotate access token using valid refresh token.
- `POST /api/v1/auth/mfa/setup` - Generate TOTP secret and QR code.
- `POST /api/v1/auth/mfa/verify` - Confirm TOTP code and enable MFA.
- `POST /api/v1/auth/logout` - Revoke current session and blacklist refresh token in Redis.
- `GET  /api/v1/auth/me` - Fetch profile, role permissions, and active tenant context.

### Module 2: Organization Management
- `GET  /api/v1/organizations/profile` - Fetch active tenant profile and legal details.
- `PATCH /api/v1/organizations/profile` - Update company profile and operating preferences.
- `GET  /api/v1/facilities` - List manufacturing plants, warehouses, and hubs.
- `POST /api/v1/facilities` - Register a new facility with geofence radius.
- `GET  /api/v1/facilities/{facility_id}/docks` - List loading docks for a plant.
- `POST /api/v1/facilities/{facility_id}/docks` - Create/configure loading docks.

### Module 3: Role-Based Access Control & User Admin
- `GET  /api/v1/users` - List organization users (filterable by role, status, facility).
- `POST /api/v1/users/invite` - Send email invitation with role assignment.
- `PATCH /api/v1/users/{user_id}` - Update user roles, facility scoping, or active status.
- `GET  /api/v1/rbac/permissions` - List all system permissions and descriptions.

### Module 4: Operations Dashboard & Metrics
- `GET  /api/v1/dashboard/metrics` - Fetch summary counters (active, at-risk, failed, in-transit).
- `GET  /api/v1/dashboard/pipeline` - Grouped shipment counts across operational stages.
- `GET  /api/v1/dashboard/map-nodes` - GeoJSON summary of active in-transit shipments.
- `GET  /api/v1/dashboard/alerts` - List active critical operational alerts.

### Module 5: Shipment Management
- `GET  /api/v1/shipments` - Filterable paginated list (status, origin, destination, date range).
- `POST /api/v1/shipments` - Create a new shipment order.
- `GET  /api/v1/shipments/{id}` - Full shipment detail including cargo, stops, and current status.
- `PATCH /api/v1/shipments/{id}` - Update cargo or pickup window (allowed in `DRAFT` only).
- `POST /api/v1/shipments/{id}/cancel` - Cancel a shipment order with audit reason.
- `POST /api/v1/shipments/{id}/documents` - Upload e-Way Bill, invoice, or packing list.

### Module 6: Transporter Master & Rate Cards
- `GET  /api/v1/transporters` - List approved carrier partners with reliability scores.
- `POST /api/v1/transporters/invite` - Onboard a carrier partner into the shipper's panel.
- `GET  /api/v1/rate-cards` - List lane rate contracts.
- `POST /api/v1/rate-cards` - Create/update lane rate cards (per-ton, per-km, detention terms).

### Module 7 & 8: Fleet & Driver Management (Carrier Portal)
- `GET  /api/v1/vehicles` - List carrier fleet assets with compliance expiry status.
- `POST /api/v1/vehicles` - Register vehicle (RC, insurance, fitness docs).
- `GET  /api/v1/drivers` - List driver roster.
- `POST /api/v1/drivers` - Register driver with driving license KYC.

### Module 9: Transporter Matching Engine
- `POST /api/v1/matching/shipments/{id}/tender` - Initiate matching (Waterfall / Broadcast / Pro-rata).
- `GET  /api/v1/matching/shipments/{id}/candidates` - Ranked list of eligible carriers for the lane.
- `GET  /api/v1/matching/tenders/pending` - Carrier view of pending load tenders.
- `POST /api/v1/matching/tenders/{tender_id}/accept` - Carrier accepts load tender.
- `POST /api/v1/matching/tenders/{tender_id}/reject` - Carrier rejects tender with mandatory reason code.

### Module 10: Booking & Dispatch
- `GET  /api/v1/bookings` - List confirmed bookings.
- `GET  /api/v1/bookings/{id}` - Detailed booking view with nominated vehicle and driver.
- `POST /api/v1/bookings/{id}/nominate` - Carrier nominates compliant vehicle and driver.
- `POST /api/v1/bookings/{id}/dispatch-order` - Generate digital Lorry Receipt / Bilty.

### Module 11: Pickup Accountability & Gate Operations
- `POST /api/v1/pickup/{shipment_id}/confirm-readiness` - Transporter confirms truck positioning.
- `POST /api/v1/pickup/{shipment_id}/gate-in/initiate` - Driver arrives at gate; triggers 6-digit OTP to driver phone.
- `POST /api/v1/pickup/{shipment_id}/gate-in/verify` - Security officer verifies OTP + checklist.
- `POST /api/v1/pickup/{shipment_id}/dock-berth` - Record dock assignment and tare weighment.
- `POST /api/v1/pickup/{shipment_id}/loading-finish` - Record gross weighment and loading finish.
- `POST /api/v1/pickup/{shipment_id}/gate-out` - Issue gate pass and mark departed.
- `POST /api/v1/pickup/{shipment_id}/override-failed` - Admin override for failed pickup state.

### Module 12: Shipment Tracking & Telematics
- `POST /api/v1/tracking/telemetry` - Ingest GPS coordinates (IoT / Driver Mobile / Webhook).
- `GET  /api/v1/tracking/shipments/{id}/live` - Fetch live location, speed, ETA, and route path.
- `GET  /api/v1/tracking/shipments/{id}/milestones` - Chronological milestone timeline.

### Module 13: Exception Management
- `POST /api/v1/exceptions` - Raise operational exception (breakdown, delay, refusal).
- `GET  /api/v1/exceptions/active` - List unresolved operational exceptions.
- `POST /api/v1/exceptions/{id}/resolve` - Mark exception resolved with action report.
- `POST /api/v1/exceptions/{id}/transship` - Reassign cargo to replacement vehicle.

### Module 14: AI Logistics Coordinator
- `GET  /api/v1/ai/risk-analysis/{shipment_id}` - Predict probability of pickup failure or delay.
- `GET  /api/v1/ai/recovery-options/{shipment_id}` - AI-recommended recovery cascade actions.
- `POST /api/v1/ai/assistant/query` - Natural language operations query assistant.

### Module 15: Proof of Delivery (POD)
- `POST /api/v1/pod/{shipment_id}/upload` - Submit e-POD (signature, photos, shortage/damage data).
- `GET  /api/v1/pod/{shipment_id}` - Fetch verified POD documents and SHA-256 hash.
- `POST /api/v1/pod/{shipment_id}/verify` - Shipper approves or flags discrepancy on POD.

### Module 16: Reconciliation & Freight Audit
- `GET  /api/v1/reconciliation/shipments/{id}` - View 3-way match sheet (Contract + Gate + Invoice).
- `POST /api/v1/reconciliation/{id}/approve` - Approve payment voucher.
- `POST /api/v1/reconciliation/{id}/dispute` - Issue formal billing discrepancy notice.

### Module 17: Analytics & Reporting
- `GET  /api/v1/analytics/otif` - On-Time In-Full metrics aggregated by lane, plant, and carrier.
- `GET  /api/v1/analytics/transporter-scorecards` - Carrier performance benchmark rankings.
- `GET  /api/v1/analytics/freight-spend` - Cost per ton-km and detention cost breakdown.

### Module 18: Integration Monitoring
- `GET  /api/v1/integrations/health` - Status of ERP, telematics, and external webhook connections.
- `GET  /api/v1/integrations/dlq` - Dead-letter queue entries.
- `POST /api/v1/integrations/dlq/{id}/retry` - Trigger manual re-processing of failed message.

### Module 19: Webhooks & Event Streaming
- `GET  /api/v1/webhooks/subscriptions` - List registered tenant webhook endpoints.
- `POST /api/v1/webhooks/subscriptions` - Register a new webhook endpoint with event filters.
- `POST /api/v1/webhooks/subscriptions/{id}/test` - Dispatch sample HMAC-signed test event.

### Module 20: Immutable Audit Trail
- `GET  /api/v1/audit/records` - Query immutable audit ledger (filter by entity, actor, date range).
- `GET  /api/v1/audit/entities/{entity_type}/{entity_id}` - Chronological audit history of an entity.

---

## 3. WebSocket Real-Time Event Gateway

**Endpoint**: `/ws/v1/events`

### Authentication Handshake
Clients connect with an authorization ticket obtained via `POST /api/v1/auth/ws-ticket` (valid for 60 seconds) or via `Authorization: Bearer <token>` in the initial WebSocket upgrade header.

### Channel Subscriptions
- `tenant:{tenant_id}:ops` - Platform alerts, SLA breaches, failed pickups.
- `shipment:{shipment_id}:tracking` - Live GPS telemetry pings and geofence events.
- `facility:{facility_id}:gate` - Live gate-in, dock berthing, and loading progress updates.
