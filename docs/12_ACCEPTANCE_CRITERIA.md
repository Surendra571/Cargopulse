# 12. Module-by-Module Acceptance Criteria (Gherkin/BDD)

This document provides formal, testable Given-When-Then acceptance criteria across all 20 core platform modules.

---

### Module 1: Authentication & Identity Management
```gherkin
Feature: Multi-Tenant Authentication & Session Management
  Scenario: Successful login with valid credentials
    Given a registered user "planner@manufacturer.com" belonging to tenant "Acme Industries"
    When the user submits valid email and password credentials
    Then the system returns a 200 OK response with a short-lived JWT access token
    And sets an HTTP-only, Secure refresh token cookie
    And the access token payload contains user_id, tenant_id, and role "DISPATCHER"

  Scenario: Prevent cross-tenant token forgery
    Given a valid JWT token issued for tenant "Beta Corp"
    When the client attempts to access endpoints for tenant "Acme Industries"
    Then the system rejects the request with HTTP 403 Forbidden or 404 Not Found
```

---

### Module 2: Organization Management
```gherkin
Feature: Organization and Facility Management
  Scenario: Create manufacturing facility with geofence
    Given an authenticated "SHIPPER_ADMIN" of tenant "Acme Industries"
    When the admin submits a new facility with code "PLANT-01", address, and geofence radius 250 meters
    Then the facility record is persisted in PostgreSQL
    And a unique constraint prevents creating another facility with code "PLANT-01" in the same tenant
```

---

### Module 3: Role-Based Access Control
```gherkin
Feature: Server-Side Authorization Enforcement
  Scenario: Gate security officer prohibited from creating shipments
    Given an authenticated user with role "GATE_SECURITY_OFFICER"
    When the user sends a POST request to "/api/v1/shipments"
    Then the server immediately returns HTTP 403 Forbidden with error code "INSUFFICIENT_PERMISSIONS"
    And no database transaction is opened
```

---

### Module 4: Operations Dashboard
```gherkin
Feature: Real-Time Operational Cockpit Updates
  Scenario: Instant alert push on failed pickup
    Given an active dispatcher connected to the dashboard WebSocket channel
    When a shipment's status transitions to "PICKUP_FAILED_CRITICAL"
    Then the WebSocket server broadcasts an alert payload within 250 milliseconds
    And the dashboard KPI tile "At Risk / Failed Pickups" increments by 1
```

---

### Module 5: Shipment Management
```gherkin
Feature: Shipment Order Lifecycle Validation
  Scenario: Disallow shipment cancellation after truck dispatch
    Given an active shipment in state "DISPATCHED"
    When a dispatcher attempts to POST to "/api/v1/shipments/{id}/cancel"
    Then the system rejects the mutation with HTTP 400 Bad Request
    And the error code states "ILLEGAL_STATE_TRANSITION"
    And the shipment remains in state "DISPATCHED"
```

---

### Module 6: Transporter Management
```gherkin
Feature: Transporter Onboarding & Rate Card Maintenance
  Scenario: Enforce unique lane rate cards
    Given an active rate card between Shipper A and Carrier B for lane "Plant-01 -> Mumbai" (FLATBED_32FT)
    When a user attempts to create an overlapping rate card for the same vehicle class and valid date range
    Then the system rejects the insertion with a unique constraint violation error
```

---

### Module 7 & 8: Fleet & Driver Management
```gherkin
Feature: Fleet Asset & Driver Compliance Verification
  Scenario: Block nomination of expired vehicle fitness certificate
    Given a transporter vehicle whose fitness certificate expired on "2026-10-01"
    When the carrier dispatcher attempts to nominate this vehicle for booking "BK-9021"
    Then the system rejects the nomination with code "VEHICLE_COMPLIANCE_EXPIRED"
    And the booking status remains "ACCEPTED" awaiting a compliant vehicle
```

---

### Module 9: Transporter Matching Engine
```gherkin
Feature: Waterfall Tendering Cascade
  Scenario: Automatic cascade upon carrier timeout
    Given a shipment tendered to Carrier 1 with a 45-minute countdown SLA
    When the 45-minute timer elapses without Carrier 1 accepting
    Then the system automatically marks Tender 1 as "EXPIRED"
    And immediately issues Tender 2 to Carrier 2 with a new 45-minute timer
    And emits a tender cascade audit event
```

---

### Module 10: Booking & Dispatch
```gherkin
Feature: Dispatch Order Generation
  Scenario: Generate scannable Lorry Receipt / Bilty
    Given a booking with a confirmed vehicle and licensed driver
    When the dispatcher clicks "Generate Dispatch Order"
    Then a digital Lorry Receipt is produced with a cryptographically signed QR code
    And the shipment transitions to "COMMITTED"
```

---

### Module 11: Pickup Accountability Engine
```gherkin
Feature: Two-Factor Gate Check-in & Detention Tracking
  Scenario: Successful physical gate check-in via OTP
    Given a nominated driver arriving at the plant gate
    When the gate security officer submits the shipment ID
    Then the system generates a 6-digit dynamic OTP sent to the driver's registered mobile number
    When the officer inputs the matching 6-digit OTP
    Then the system records the event "GATE_IN" with the current UTC timestamp
    And the shipment status transitions to "GATE_IN"
    And the free detention countdown timer (4 hours) starts ticking

  Scenario: Automated failed pickup detection
    Given a confirmed booking with pickup window ending at "14:00 UTC"
    And nomination cutoff defined as "10:00 UTC"
    When the time reaches "10:01 UTC" and no vehicle has been nominated
    Then the background Celery worker updates shipment status to "PICKUP_FAILED_CRITICAL"
    And publishes an urgent recovery event to the Shipper Operations channel
```

---

### Module 12: Shipment Tracking & Telematics
```gherkin
Feature: GPS Telematics & Geofence Detection
  Scenario: Consignee geofence entry auto-detection
    Given an in-transit vehicle transmitting GPS coordinates
    When a telemetry ping arrives with coordinates within 300 meters of the consignee destination
    Then the system records a milestone "ARRIVED_DESTINATION"
    And broadcasts an arrival notification to the receiving dock team
```

---

### Module 13: Exception Management
```gherkin
Feature: Cargo Transshipment on Vehicle Breakdown
  Scenario: Transship cargo to replacement vehicle
    Given an active shipment halted due to "VEHICLE_BREAKDOWN"
    When the carrier dispatcher registers a replacement vehicle "MH-04-CD-5678" with valid fitness
    And the driver confirms cargo transfer completion
    Then the system binds the new vehicle to the active shipment
    And logs a "CARGO_TRANSSHIPPED" audit entry with location coordinates
    And resumes active tracking
```

---

### Module 14: AI Logistics Coordinator
```gherkin
Feature: Predictive Pickup Failure Risk
  Scenario: Risk scoring based on telematics and carrier history
    Given a carrier scheduled for pickup in 2 hours
    And the driver's current GPS location is 180 km away in heavy traffic
    When the AI risk assessment task evaluates the shipment
    Then the system outputs a "HIGH_RISK" flag (Probability of failure > 85%)
    And recommends immediate standby truck alert
```

---

### Module 15: Proof of Delivery (e-POD)
```gherkin
Feature: Tamper-Evident e-POD Submission
  Scenario: Upload e-POD with SHA-256 hash
    Given an arrived vehicle at the consignee
    When the driver uploads the signed delivery challan photo and consignee digital signature
    Then the system computes the SHA-256 hash of the payload and image binary
    And saves the record to "pod_records"
    And transitions the shipment to "DELIVERED"
    And verifies that the hash cannot be mutated by subsequent updates
```

---

### Module 16: Reconciliation & Freight Audit
```gherkin
Feature: Three-Way Invoice Match Engine
  Scenario: Auto-approve matching carrier invoice
    Given a shipment with contracted rate $500.00
    And gate-in to gate-out dwell time of 6 hours (2 hours billable detention @ $15/hr = $30.00)
    When the carrier submits an invoice for $530.00
    Then the 3-way match engine calculates payable amount as $530.00 (Discrepancy: $0.00)
    And automatically marks the record as "AUTO_MATCHED"
    And creates a payment approval voucher
```

---

### Module 17: Analytics & Reporting
```gherkin
Feature: OTIF & Transporter Scorecard Calculation
  Scenario: Accurate monthly carrier placement ratio
    Given Transporter A was tendered 100 shipments in November
    And accepted and positioned 92 within SLA
    When the monthly analytics rollup runs
    Then Transporter A's placement reliability is reported as exactly 92.00%
```

---

### Module 18: Integration Monitoring
```gherkin
Feature: Dead-Letter Queue & Retry Management
  Scenario: Retry failed ERP outbound sync
    Given a failed SAP shipment sync message in the DLQ due to temporary SAP network timeout
    When an integration admin clicks "Retry Message"
    Then the system re-queues the message to Celery
    And upon successful HTTP 200 from SAP, marks the DLQ entry as "RESOLVED"
```

---

### Module 19: Webhooks & Event Streaming
```gherkin
Feature: Cryptographic Outbound Webhook Delivery
  Scenario: Deliver HMAC-signed shipment update
    Given a registered tenant webhook endpoint "https://erp.shipper.com/webhook"
    When a shipment transitions to "DISPATCHED"
    Then the webhook worker sends a POST request with header "X-CargoPulse-Signature"
    And the signature matches HMAC-SHA256(secret, timestamp + "." + body)
```

---

### Module 20: Immutable Audit Trail
```gherkin
Feature: Non-Repudiation Audit Ledger
  Scenario: Audit entry emitted on rate card override
    Given a logistics manager overriding a contracted rate from $450 to $480
    When the database transaction commits
    Then an audit record is created in "audit_ledger" containing:
      | actor_id      | manager_uuid        |
      | action        | RATE_OVERRIDE       |
      | previous_rate | 450.00              |
      | new_rate      | 480.00              |
      | timestamp     | CURRENT_TIMESTAMP   |
    And verifying that database user cannot delete or update this record
```
