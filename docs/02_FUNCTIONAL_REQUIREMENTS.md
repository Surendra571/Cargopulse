# 02. Functional Requirements Specification

This document details the functional requirements across all **20 Core Modules** of CargoPulse.

---

## Module 1: Authentication & Identity Management
- **FR-1.1 Multi-Tenant Identity**: Support user registration, credential login (email/password with bcrypt hashing), and enterprise Single Sign-On (SAML 2.0 / OIDC) for enterprise shipper tenants.
- **FR-1.2 Session & Token Security**: Secure short-lived JWT access tokens (15-minute expiration) coupled with cryptographically random refresh tokens stored in Redis with revocation capabilities.
- **FR-1.3 Multi-Factor Authentication (MFA)**: Time-based One-Time Password (TOTP) support mandatory for administrative and finance roles; SMS/WhatsApp OTP fallback for field operations.
- **FR-1.4 Tenant Scoping**: Authenticated session context must inject the active `tenant_id`, user role, and permission grants into every request context.

---

## Module 2: Organization Management
- **FR-2.1 Organization Profiles**: Maintain detailed legal entity records: Legal Name, Trade Name, GSTIN / Tax ID, Registered Address, Billing Address, Operating Hubs/Plants/Warehouses.
- **FR-2.2 Multi-Branch & Plant Hierarchy**: Shippers can define hierarchical organizational structures (Enterprise Headquarters $\rightarrow$ Regional Operating Zones $\rightarrow$ Manufacturing Plants / Warehouses $\rightarrow$ Loading Docks).
- **FR-2.3 Transporter Partnerships**: Shippers can invite, onboard, and maintain approved transporter vendor lists with contract validity windows.
- **FR-2.4 Document Repository**: Storage and expiry tracking for organization compliance documents (Trade licenses, MSME certificates, insurance policies).

---

## Module 3: Role-Based Access Control (RBAC)
- **FR-3.1 System Default Roles**: Support out-of-the-box standard roles:
  - Shipper: `OrgAdmin`, `LogisticsManager`, `Dispatcher`, `GateOfficer`, `FinanceAuditor`, `ReadOnlyViewer`.
  - Transporter: `CarrierAdmin`, `CarrierDispatcher`, `DriverUser`.
  - Platform: `SuperAdmin`, `SupportEngineer`.
- **FR-3.2 Custom Roles & Granular Permissions**: Ability for Org Admins to create custom roles by toggling granular permissions (e.g., `shipments:create`, `bookings:tender`, `rates:view`, `reconciliation:approve`).
- **FR-3.3 Facility-Level Scoping**: Restrict specific operational users (e.g., Gate Officers) to assigned physical plants/docks only.

---

## Module 4: Operations Dashboard
- **FR-4.1 Real-Time Operational Cockpit**: Live KPI metrics: Active Shipments, Pickups Scheduled Today, At-Risk Pickups, Failed Pickups, In-Transit Exceptions, Unreconciled PODs.
- **FR-4.2 Visual Pipeline Board**: Kanban and tabular views of shipments organized by operational stages: `DRAFT` $\rightarrow$ `ALLOCATED` $\rightarrow$ `COMMITTED` $\rightarrow$ `GATE_IN` $\rightarrow$ `LOADING` $\rightarrow$ `DISPATCHED` $\rightarrow$ `IN_TRANSIT` $\rightarrow$ `DELIVERED` $\rightarrow$ `RECONCILED`.
- **FR-4.3 Interactive Map View**: Geo-spatial visualization of active fleet locations, pickup origins, delivery destinations, and delayed routes.
- **FR-4.4 Real-Time Alerts Drawer**: Instant WebSocket notifications for SLA breaches, driver SOS, gate dwell time violations, and failed commitments.

---

## Module 5: Shipment Management
- **FR-5.1 Shipment Order Creation**: Ingestion of shipment requests via manual UI forms or automated ERP integration (REST / Webhook) containing:
  - Consignor (Pickup location, plant, dock, target pickup window).
  - Consignee (Delivery address, contact details, target delivery window).
  - Cargo Profile (Commodity type, weight, volume, pallet count, hazardous material flags, temperature constraints).
  - Commercial details (Invoice reference, declared cargo value).
- **FR-5.2 Multi-Leg & Consolidation**: Support for single-origin single-destination (FTL), multi-stop pickups, and split dispatches.
- **FR-5.3 Status Lifecycle Engine**: Strict validation of state transitions preventing illegal jumps (e.g., cannot mark `IN_TRANSIT` without a valid `DISPATCHED` state and gate-out timestamp).
- **FR-5.4 Cargo Document Attachments**: Attaching e-way bills, commercial invoices, packing lists, and Material Safety Data Sheets (MSDS).

---

## Module 6: Transporter Management
- **FR-6.1 Transporter Directory**: Comprehensive carrier master profile including fleet size, authorized lanes/corridors, vehicle types supported, and insurance coverage.
- **FR-6.2 Rate Card & Contract Management**: Storage of lane-level contracted rates (Per Ton, Per Km, Flat Trip Rate, Fuel Surcharge Matrix, Detention Slab Rates).
- **FR-6.3 Performance Scorecarding**: Rolling calculations of carrier metrics:
  - Placement Ratio: $\frac{\text{Placements within SLA}}{\text{Tenders Accepted}}$.
  - On-Time Pickup Rate (OTP).
  - On-Time Delivery Rate (OTD).
  - Incident / Rejection Rate.
- **FR-6.4 Vendor Blacklisting / Suspension**: Capability to temporarily or permanently suspend transporters from lane tendering based on compliance violations or chronic failure.

---

## Module 7: Vehicle Management
- **FR-7.1 Fleet Asset Registry**: Register vehicles by registration number, vehicle class (Flatbed, Closed Container, Refrigerated, Tanker), payload capacity (Tons/Cu.Ft), axle count, and make/model.
- **FR-7.2 Compliance & Document Expiry Tracking**: Mandatory validation of Registration Certificate (RC), National/State Permits, Fitness Certificate, Road Tax, and Third-Party Pollution/Insurance.
- **FR-7.3 Telematics & GPS Integration**: Support for hardware GPS tracker ID mapping, FASTag / toll RFID tracking identifiers, and mobile telemetry associations.
- **FR-7.4 Maintenance & Blacklist Status**: Real-time vehicle availability flags (`ACTIVE`, `MAINTENANCE`, `IMPOUNDED`, `BLACKLISTED`).

---

## Module 8: Driver Management
- **FR-8.1 Driver Master Records**: Full name, mobile phone number, secondary contact, permanent address, language preferences, emergency contact.
- **FR-8.2 KYC & Driving License Verification**: License number, issuing RTO, authorized vehicle classes, license validity date, biometric/photo capture.
- **FR-8.3 Safety & Incident History**: Logging of past accident reports, alcohol/safety violations at factory gates, and customer conduct ratings.
- **FR-8.4 Driver App / SMS Link Allocation**: Mechanism to send secure temporary mobile web links or native app tokens for active trips.

---

## Module 9: Transporter Matching Engine
- **FR-9.1 Multi-Mode Allocation Algorithms**:
  - *Contracted Share of Business (SoB)*: Pro-rata allocation based on pre-agreed monthly lane quotas (e.g., Carrier A: 50%, Carrier B: 30%, Carrier C: 20%).
  - *Ranked Waterfall Tendering*: Sequential tendering to Carrier 1 with a response countdown timer (e.g., 45 minutes); auto-cascades to Carrier 2 upon rejection or timeout.
  - *Spot Broadcast Bidding*: Reverse auction where registered lane carriers place competitive bids within a defined bidding window.
  - *Performance-Weighted Dynamic Allocation*: Preferential ranking based on carrier OTP and placement reliability scores.
- **FR-9.2 Auto-Trigger Logic**: Automatic trigger of matching upon shipment order release from draft or ERP sync.
- **FR-9.3 Rejection Reason Tracking**: Mandatory structured reason capture when a carrier declines a tender (e.g., "No vehicles in corridor", "Rate unviable", "Dock loading delay history").

---

## Module 10: Booking & Dispatch
- **FR-10.1 Booking Order Lifecycle**: Generation of formal Booking Orders binding the Shipper and matched Transporter with agreed pickup slot, vehicle type, and freight terms.
- **FR-10.2 Vehicle & Driver Nomination**: Transporter must formally nominate a compliant vehicle and licensed driver before the nomination SLA cutoff.
- **FR-10.3 Dispatch Order Generation**: Production of digital Dispatch Orders (Goods Consignment Note / Lorry Receipt / Bilty) with unique scannable barcodes/QR codes.
- **FR-10.4 Cancellation & Reallocation Protocols**: Rules governing cancellations, cancellation fee penalties, and automatic re-triggering of the matching engine.

---

## Module 11: Pickup Accountability Engine (Core Differentiator)
- **FR-11.1 Proactive Commitment Checkpoints**: Automated outbound verification triggers sent to Transporter Dispatcher and Driver:
  - $T-4$ Hours: "Confirm truck positioning intent & current GPS distance".
  - $T-2$ Hours: "Confirm vehicle en route to plant".
  - $T-1$ Hour: "Final approach verification".
- **FR-11.2 Digital Gate Check-in & Geo-fencing**:
  - Driver triggers arrival via Geo-fence entry detection ($\le 200\text{m}$ of plant perimeter) or scans physical QR code at the security gate.
  - Two-Factor Gate Pass: Delivery of a 6-digit dynamic OTP to the driver's phone, verified by the plant security officer.
- **FR-11.3 Dock Queue & Dwell Time Auditing**:
  - Precise automated timestamps: `GATE_ARRIVAL`, `GATE_ENTRY`, `DOCK_BERTHED`, `LOADING_STARTED`, `LOADING_COMPLETED`, `TARE_WEIGHED`, `GROSS_WEIGHED`, `GATE_EXIT`.
  - Automatic calculation of Free Detention Time vs. Billable Detention Hours.
- **FR-11.4 Automated Failed Pickup Detection**:
  - If a carrier has not nominated a vehicle by $T-X$ hours, OR driver is $> 50\text{km}$ away at $T-1$ hour with impossible transit time, OR vehicle fails to enter the gate by the pickup window cutoff:
  - System automatically flags shipment as `PICKUP_FAILED_CRITICAL`.
  - Sends immediate alerts to Shipper Ops and invokes recovery workflows.

---

## Module 12: Shipment Tracking & Telematics
- **FR-12.1 Multi-Source Telematics Ingestion**:
  - GPS hardware providers via standardized REST/Webhook adapter.
  - SIM-based cellular tower triangulation (with driver consent).
  - Driver mobile device GPS coordinates sampled at configurable intervals (e.g., every 5 minutes in motion, 15 minutes stationary).
- **FR-12.2 Milestone Generation Engine**: Automated detection of milestone events (Passed Transit Hub, State Border Crossing, Rest Stop, Approaching Consignee Geo-fence).
- **FR-12.3 Predictive ETA & Delay Forecasting**: Calculation of Estimated Time of Arrival factoring road network restrictions, heavy vehicle speed profiles, and mandatory driver rest periods.
- **FR-12.4 Route Deviation & Geo-fence Breach Alerts**: Instant alerting when a vehicle deviates by more than $X$ km from the authorized corridor or halts unscheduled for $> 60$ minutes.

---

## Module 13: Exception Management
- **FR-13.1 Exception Categorization**:
  - Missed / Failed Pickup.
  - Vehicle Breakdown / Technical Failure.
  - Transit Accident / Damage / Spill.
  - Route Delay / Traffic / Weather Blockade.
  - Consignee Refusal / Dock Unavailable.
  - Documentation Issue (e-Way Bill expired / mismatch).
- **FR-13.2 Automated Escalation Matrix**: Tiered notification workflows (Level 1: Ops Coordinator $\rightarrow$ Level 2: Logistics Head $\rightarrow$ Level 3: Supply Chain VP) with configurable SLA escalation timers.
- **FR-13.3 Recovery Orchestration**: Workflow for initiating vehicle transshipment (transferring cargo from broken-down vehicle to replacement vehicle with cross-dock inspection logs).
- **FR-13.4 Dispute Resolution Logging**: Centralized communication log between Shipper and Transporter to agree upon fault attribution and financial liability.

---

## Module 14: AI Logistics Coordinator
- **FR-14.1 Predictive Risk Assessment**: Machine learning scoring model evaluating the probability of pickup failure based on carrier historical reliability, lane congestion, weather forecasts, and day-of-week patterns.
- **FR-14.2 Automated Recovery Dispatch Recommendations**: Real-time generation of optimal fallback options when a pickup fails (e.g., "Re-tender to Carrier B at +4% rate vs. call internal buffer truck at Hub 2").
- **FR-14.3 Anomaly Detection**: Unsupervised pattern detection for suspicious dwell times, route diversions, or fuel theft indicators.
- **FR-14.4 Natural Language Operations Assistant**: AI-powered natural language query engine for dispatchers (e.g., *"Show all delayed cement shipments to Ahmedabad and draft escalation emails to Transporter X"*).

---

## Module 15: Proof of Delivery (POD)
- **FR-15.1 Digital e-POD Capture**:
  - Geo-tagged, timestamped digital signature from the consignee receiving officer.
  - High-resolution camera photograph upload of the physical signed Lorry Receipt / Delivery Challan.
  - Photographs of unloaded cargo showing packaging condition and seal integrity.
- **FR-15.2 Shortage, Damage & Discrepancy Recording (SDD)**:
  - Line-item cargo condition check (Received Quantity vs. Dispatched Quantity).
  - Explicit logging of broken seals, water damage, carton crush, or expired goods with photographic proof.
- **FR-15.3 Tamper-Evident Hashing**: Cryptographic hash (SHA-256) of the uploaded POD document, signature, geo-location, and timestamp committed to the audit trail to prevent retroactive alteration.
- **FR-15.4 Instant Invoicing Trigger**: Successful POD verification automatically transitions the shipment to the `RECONCILIATION_READY` state.

---

## Module 16: Reconciliation & Freight Audit
- **FR-16.1 Three-Way Match Engine**: Automated comparison between:
  1. Original Contract / Booking Rate Card.
  2. Operational Execution Logs (Weight tickets, verified detention hours from gate logs, toll charges).
  3. Transporter Submitted Invoice & Verified POD.
- **FR-16.2 Detention & Penalty Computation**: Transparent rule-based calculation of detention charges (subtracting agreed free time from verified gate-to-gate dwell time) and late-delivery penalty deductions.
- **FR-16.3 Discrepancy Approval Workflows**: Discrepancies exceeding configurable monetary thresholds (e.g., $> \$25$ or $> 2\%$) automatically route to Finance Managers for approval or dispute counter-claims.
- **FR-16.4 ERP Accounts Payable Export**: Export of approved freight payment vouchers in structured JSON/XML/CSV formats for direct ERP ingestion.

---

## Module 17: Analytics & Reporting
- **FR-17.1 On-Time In-Full (OTIF) Reporting**: Comprehensive analysis of delivery timeliness and quantity accuracy split by plant, transporter, customer, and lane.
- **FR-17.2 Transporter Scorecarding**: Multi-dimensional benchmarking of carriers across placement speed, pickup adherence, transit reliability, and billing accuracy.
- **FR-17.3 Cost & Efficiency Analytics**: Total freight spend, cost per ton-kilometer, detention expenditure breakdown, and empty-run waste analysis.
- **FR-17.4 Scheduled & Exportable Reports**: Automated scheduling of weekly/monthly executive summaries delivered via email and exportable to Excel, CSV, and PDF.

---

## Module 18: Integration Monitoring
- **FR-18.1 Enterprise Connector Status**: Real-time health monitoring of upstream ERP connections (SAP, Oracle, NetSuite) and downstream telematics partners.
- **FR-18.2 Ingestion & Sync Telemetry**: Tracking sync throughput, API latency, record count parity, and processing failures.
- **FR-18.3 Dead-Letter Queue (DLQ) Management**: Visual interface to inspect failed ERP sync messages, view stack traces, edit payloads, and trigger manual or batch retries.
- **FR-18.4 Integration Alerts**: PagerDuty/Slack/Email notifications triggered when error rates exceed defined thresholds (e.g., $> 1\%$ over a 5-minute window).

---

## Module 19: Webhooks & Event Streaming
- **FR-19.1 Outbound Webhook Subscriptions**: External systems can register webhook endpoints to subscribe to granular events (`shipment.created`, `pickup.confirmed`, `pickup.failed`, `tracking.milestone`, `pod.verified`, etc.).
- **FR-19.2 Cryptographic Delivery Verification**: Every outbound webhook request signed using HMAC-SHA256 with a tenant-specific shared secret header (`X-CargoPulse-Signature`).
- **FR-19.3 Resilient Delivery Engine**: Exponential backoff retry policy (1m, 5m, 15m, 1h, 6h, 24h) with automated circuit breaker tripping after 50 consecutive delivery failures.
- **FR-19.4 Event Replay Capability**: Self-service portal for developers to view delivery request/response headers, status codes, latencies, and replay past events.

---

## Module 20: Immutable Audit Trail
- **FR-20.1 Comprehensive System Ledger**: Every state mutation across the entire platform must generate an immutable audit record containing:
  - `event_id` (UUIDv7, monotonically time-ordered).
  - `tenant_id`.
  - `entity_type` (e.g., `Shipment`, `Booking`, `RateCard`, `GateEntry`).
  - `entity_id`.
  - `action` (`CREATE`, `UPDATE`, `STATUS_TRANSITION`, `DELETE_SOFT`, `OVERRIDE`).
  - `actor_id` and `actor_type` (`USER`, `API_KEY`, `SYSTEM_JOB`, `AI_AGENT`).
  - `ip_address` and `user_agent`.
  - `previous_state` (JSON snapshot).
  - `new_state` (JSON snapshot).
  - `diff` (JSON delta).
  - `created_at` (Immutable UTC timestamp).
- **FR-20.2 Non-Repudiation & Tamper Evidence**: Audit records stored in append-only tables; no user or administrative role has `UPDATE` or `DELETE` privileges.
- **FR-20.3 Search & Compliance Audits**: High-performance querying across audit records filtered by entity, actor, date range, or event type, exportable for ISO/SOC2 regulatory compliance.
