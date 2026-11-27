# Transporter Integration Guide

## Overview

CargoPulse integrates with external transporter TMS platforms, GPS telemetry providers, and ERP systems through an **idempotent webhook & retry architecture** (`/api/v1/integrations`).

## Outbound Webhooks

- **Signature Verification**: Outbound webhook payloads are signed with HMAC-SHA256 (`X-CargoPulse-Signature`) so carrier endpoints can verify authenticity.
- **Retry Policy**: Transient `5xx`, `429`, or network timeout failures are retried with exponential backoff via the Celery `notifications` / `default` queues.
- **Dead-Letter Queue (DLQ)**: Events exhausting max retries are persisted to the DLQ (`/integrations/dlq`) with full payload, status code, and error trace for operator inspection and manual replay.

## Inbound Telemetry & Tracking

- **Endpoint**: `POST /api/v1/tracking/telemetry` (and milestone updates via `/api/v1/tracking/milestones`).
- **Idempotency**: Duplicate telemetry events with identical `(shipment_id, event_timestamp, event_type)` or idempotency keys are safely deduplicated.
- **Real-Time Propagation**: Validated milestones update shipment status, recalculate ETA variance, and append immutable `shipment_events`.

## Pickup Commitment & Accountability

- Carriers confirm pickup windows (`COMMITTED`), transition to `STARTED` when dispatching, or trigger `MISSED` SLA breaches when pickup deadlines expire without arrival.
- Missed pickups automatically open recovery cases in the **Missed Pickup Recovery Center** (`/recovery`).
