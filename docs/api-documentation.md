# API Documentation

## Base URL & Envelope

- **Base Prefix**: `/api/v1`
- **Interactive OpenAPI (Development only)**: `/api/v1/docs` and `/api/v1/redoc` (automatically disabled when `ENVIRONMENT=production` and `DEBUG=false`).
- **Authentication**: Bearer JWT in `Authorization: Bearer <access_token>` plus `HttpOnly` refresh cookie (`cargopulse_refresh_token`) and double-submit CSRF header (`X-CSRF-Token`) on cookie-authenticated mutations.

## Endpoint Groups

| Module | Prefix | Description |
| :--- | :--- | :--- |
| Health & Probes | `/api/v1/healthz` | `GET ""` (overview), `GET /live`, `GET /ready` (503 if DB/Redis down) |
| Authentication | `/api/v1/auth` | `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `GET /me`, `POST /forgot-password`, `POST /reset-password` |
| Organizations & RBAC | `/api/v1/organizations` | Organization profile, members, roles, and permission assignments |
| Operations Dashboard | `/api/v1/dashboard` | KPIs, volume trends, transporter SLA gauges, recent shipments & exceptions |
| Shipments | `/api/v1/shipments` | Shipment CRUD, filtering, timeline events, status transitions |
| Matching | `/api/v1/matching` | Transporter scoring & ranked recommendations for shipments |
| Bookings | `/api/v1/bookings` | Transporter booking requests, confirmations, rejections, assignments |
| Pickup Monitoring | `/api/v1/pickup-monitoring` | Commitment windows (`COMMITTED`, `STARTED`, `MISSED`, `COMPLETED`), SLA alerts |
| Tracking | `/api/v1/tracking` | Telemetry ingestion, GPS milestones, ETA updates |
| Proof of Delivery | `/api/v1/pod` | e-POD file upload, verification status, discrepancy flagging |
| Integrations | `/api/v1/integrations` | Webhook endpoints, delivery logs, retry queue, Dead-Letter Queue (DLQ) |
| Exceptions | `/api/v1/exceptions` | Exception creation, escalation, resolution, recovery actions |
| Fleet Directory | `/api/v1/transporters`, `/vehicles`, `/drivers` | Carrier profiles, compliance status, vehicle & driver management |
| AI Coordinator | `/api/v1/ai-coordinator` | Grounded Q&A sessions, action proposals, explicit approve/reject endpoints |
| Reconciliation | `/api/v1/reconciliation` | Freight invoice vs. shipment & e-POD matching, dispute handling |
| Analytics & Audit | `/api/v1/analytics`, `/api/v1/audit` | SLA analytics, carrier scorecards, immutable audit log queries |

## Standard Error Format

All errors return a structured JSON envelope:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input validation failed. Inspect details for fields.",
    "details": [{ "field": "body.email", "issue": "value is not a valid email address" }]
  },
  "meta": {
    "timestamp": "2026-11-27T05:30:00+00:00",
    "path": "/api/v1/auth/login"
  }
}
```
