# Testing & Quality Assurance Guide

## Test Pyramid

CargoPulse enforces automated verification across backend, frontend, migrations, and production builds:

### 1. Backend Test Suite (`pytest`)
Located in `backend/tests/`:
- **Auth & RBAC**: `test_auth.py`, `test_organization_rbac.py`, `test_qa_security_audit.py` (tenant isolation, CSRF, rate limiting, role permissions)
- **Core Logistics Lifecycle**: `test_shipments.py`, `test_matching.py`, `test_bookings.py`, `test_pickup_and_exceptions.py`, `test_tracking_and_milestones.py`, `test_pod.py`
- **Reliability & Integrations**: `test_integrations_engine.py`, `test_qa_reliability.py` (webhook retries, DLQ replay, outbox)
- **AI, Reconciliation & Analytics**: `test_ai_coordinator.py`, `test_reconciliation.py`, `test_analytics_and_audit.py`
- **End-to-End Lifecycle**: `test_qa_e2e_full_lifecycle.py`, `test_qa_backend_comprehensive.py`

Run locally:
```bash
cd backend
pytest -v --tb=short
```

### 2. Frontend Test Suite (`Vitest` + `tsc`)
Located in `frontend/src/test/`:
- `auth.test.tsx`: Login & registration form validation
- `routes.test.tsx`: ProtectedRoute guard & redirect behavior

Run locally:
```bash
cd frontend
npx tsc -b
npx vitest run
npm run build
```
