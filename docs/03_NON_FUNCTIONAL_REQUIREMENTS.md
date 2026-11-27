# 03. Non-Functional Requirements (NFRs)

This document establishes the architectural, operational, performance, security, and quality benchmarks that CargoPulse must satisfy.

---

## 1. Performance & Latency Benchmarks

| Metric Category | Target SLA | Measurement Condition |
|---|---|---|
| **API Response Time (P95)** | $\le 150\text{ ms}$ | Standard CRUD, filtering, pagination queries under normal load. |
| **API Response Time (P99)** | $\le 300\text{ ms}$ | Complex relational queries, shipment timeline generation. |
| **Telemetry Ingestion Throughput** | $\ge 5,000\text{ events/sec}$ | Concurrent GPS / IoT coordinate pings ingested and processed. |
| **Telemetry Processing Latency** | $\le 1,000\text{ ms}$ | Time from telematics receipt to geofence evaluation and WebSocket broadcast. |
| **Dashboard WebSocket Broadcast** | $\le 250\text{ ms}$ | Real-time push to connected browser sessions upon milestone transition. |
| **Database Query SLA (P95)** | $\le 25\text{ ms}$ | All standard indexed tenant-filtered queries. |
| **Background Job Execution (Celery)** | $\le 2.0\text{ s}$ | P95 queue dwell time for asynchronous background tasks. |
| **Frontend Initial Load Time (LCP)** | $\le 1.8\text{ s}$ | Largest Contentful Paint on standard 4G / broadband connections. |

---

## 2. High Availability & Scalability

### 2.1 Availability Objectives
- **System Uptime**: $\ge 99.95\%$ annualized availability excluding scheduled maintenance windows.
- **Recovery Point Objective (RPO)**: $\le 1\text{ minute}$ (PostgreSQL continuous WAL archiving + streaming replication).
- **Recovery Time Objective (RTO)**: $\le 15\text{ minutes}$ for complete cluster failover to secondary availability zone.

### 2.2 Scalability Profile
- **Horizontal Scalability**:
  - Stateless FastAPI application containers scaled horizontally behind reverse proxies / cloud load balancers.
  - Celery background workers partitioned into dedicated queues (`telemetry`, `notifications`, `reconciliation`, `ai_eval`) and auto-scaled based on queue depth.
- **Database Scalability**:
  - PostgreSQL primary instance for writes with asynchronous read replicas for analytical queries and dashboard aggregations.
  - Table partitioning by time (monthly partitions) for high-volume append-only tables (`shipment_events`, `telemetry_logs`, `audit_ledger`).
- **Cache Scalability**:
  - Redis cluster handling session caching, rate limiting tokens, and Celery broker queues with sentinel-managed failover.

---

## 3. Reliability & Fault Tolerance

1. **Transaction Isolation & Atomicity**:
   - Critical multi-entity operations (e.g., Booking confirmation + vehicle allocation + milestone creation) execute within strict PostgreSQL database transactions (`READ COMMITTED` default, `REPEATABLE READ` for financial reconciliation).
2. **Idempotency Standards**:
   - All mutating API endpoints (POST/PUT/PATCH) accept an `Idempotency-Key` header.
   - Redis-backed idempotency registry caches request fingerprints for 24 hours to prevent duplicate shipments, double-bookings, or redundant gate entries.
3. **Graceful Degradation & Circuit Breaking**:
   - Third-party integrations (GPS providers, SMS/WhatsApp gateways, ERP webhooks) wrapped in circuit breakers.
   - If an external GPS vendor is down, the system smoothly falls back to cellular triangulation or mobile app updates without halting platform operations.
4. **Dead-Letter Handling (DLQ)**:
   - Celery tasks configure maximum retry limits (default: 5 retries with exponential jittered backoff).
   - Poison messages are quarantined in PostgreSQL-backed dead-letter tables with full payload and error context for operator review.

---

## 4. Multi-Tenant Security & Isolation

1. **Strict Data Boundary**:
   - No query may ever execute without an explicit `tenant_id` predicate, enforced at the SQLAlchemy repository tier.
   - Multi-tenant foreign key constraints prevent cross-tenant referencing.
2. **Authentication & Cryptography**:
   - Passwords hashed using Argon2id or bcrypt (cost factor $\ge 12$).
   - JWT tokens signed with asymmetric keys (RS256) with key rotation support.
   - Sensitive data at rest (driver KYC IDs, tax identifiers, contract rates) encrypted using AES-256-GCM.
   - All network traffic enforced over TLS 1.3 in transit.
3. **Role-Based Server-Side Authorization**:
   - Every FastAPI endpoint explicitly declares permission dependencies evaluated against the validated tenant and user session.
   - Client-side routing guards serve solely as UX conveniences; server-side guards are non-bypassable.

---

## 5. Auditability & Regulatory Compliance

1. **Immutable Audit Ledger**:
   - Append-only log of every state transition and administrative action.
   - Cryptographic chaining: Each record in `audit_ledger` computes an incremental SHA-256 hash incorporating the previous record's hash to ensure tamper-evidence.
2. **Data Retention & Archival**:
   - Active operational data retained online for 24 months.
   - Historical records archived to cold storage in compressed, queryable Parquet format with 7-year retention for tax and legal compliance.
3. **Statutory Standards Compliance**:
   - Designed to adhere to ISO/IEC 27001 (Information Security Management) and SOC 2 Type II trust principles (Security, Availability, Processing Integrity, Confidentiality).
   - Compliant with regional digital logistics guidelines (e-Way Bill standards, digital proof of delivery legality).

---

## 6. Observability & Telemetry

1. **Structured Logging**:
   - All logs emitted in structured JSON format including `timestamp`, `level`, `tenant_id`, `trace_id`, `span_id`, `service`, `module`, and `message`.
2. **Distributed Tracing**:
   - OpenTelemetry instrumentation tracing requests from frontend client $\rightarrow$ API Gateway $\rightarrow$ FastAPI service $\rightarrow$ PostgreSQL / Redis $\rightarrow$ Celery worker.
3. **Metrics & Health Probes**:
   - Prometheus metrics endpoint exposing HTTP request rates, error distributions, database connection pool statistics, Celery queue depth, and cache hit ratios.
   - Liveness (`/healthz/liveness`) and Readiness (`/healthz/readiness`) probes verifying database and Redis connectivity.
