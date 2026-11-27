# 13. Ambiguities & Sensible Architectural Defaults

During the architectural analysis of the CargoPulse platform, several real-world B2B supply chain edge cases and ambiguities were identified. This document details each ambiguity along with the **sensible, production-grade defaults** adopted in the CargoPulse architecture.

---

## 1. Pickup SLA Definition & Ambiguities

### Ambiguity
- When does a "pickup commitment" officially breach? Is it when the vehicle fails to enter the gate by the pickup window start time, the pickup window end time, or when the carrier fails to nominate a driver/vehicle by a nomination cutoff?

### Battle-Tested Default
CargoPulse adopts a **Two-Stage Pickup SLA**:
1. **Nomination Cutoff ($T_{\text{nomination}} = \text{Pickup Window Start} - 4\text{ hours}$)**:
   The transporter must formally commit a specific compliant vehicle and driver at least 4 hours before the pickup window opens. If no nomination occurs by this cutoff, the shipment transitions to `NOMINATION_SLA_BREACHED`, alerting dispatchers to re-tender or activate standby trucks.
2. **Physical Gate-In Cutoff ($T_{\text{arrival}} = \text{Pickup Window End} + 30\text{ minutes}$)**:
   The vehicle must physically arrive and complete OTP verification at the plant security gate within 30 minutes of the scheduled pickup window closing. Beyond this tolerance, the system flags `PICKUP_FAILED_CRITICAL`.

---

## 2. Gate-In Verification Without Cellular Coverage

### Ambiguity
- Many heavy manufacturing plants (steel mills, cement factories, chemical refineries) are in remote geographic areas with erratic cellular coverage. If the driver cannot receive an SMS OTP, how does gate verification proceed without compromising security?

### Battle-Tested Default
CargoPulse implements a **Hybrid Three-Way Gate Check-in Protocol**:
1. **Primary**: Dynamic 6-digit SMS / WhatsApp OTP sent to the driver's registered phone upon gate arrival.
2. **Secondary (Offline Driver App / QR Pass)**: The driver app generates a cryptographically signed, time-based offline QR code (TOTP algorithm embedded in the app) that the security officer scans using the gate camera scanner.
3. **Tertiary (Security Officer Manual Override)**: If both cellular and offline apps fail, the Gate Security Officer can execute a manual gate-in by physically inspecting and typing the driver's national driving license number and vehicle registration certificate. This action automatically generates a high-priority `SECURITY_MANUAL_OVERRIDE` audit event requiring supervisor sign-off before gate-out pass issuance.

---

## 3. Detention Time & Free-Hours Calculation Rules

### Ambiguity
- If a truck arrives at the factory gate 3 hours earlier than its scheduled pickup window, does the free detention period begin upon arrival or at the scheduled appointment start time?
- Does loading dwell time stop when cargo loading finishes, or when the security officer issues the final gate-out pass after weighbridge check?

### Battle-Tested Default
1. **Early Arrival Rule**:
   If a truck arrives earlier than the agreed pickup window, the free detention timer starts **only at the scheduled pickup window start time**. Early arrival is voluntary and does not penalize the manufacturing plant.
2. **Late Arrival Rule**:
   If a truck arrives after the pickup window opens, the free detention timer begins **at the actual verified Gate-In timestamp**.
3. **Detention Window Boundary**:
   Detention time runs from `GATE_IN` to `GATE_OUT`. However, the system logs intermediate timestamps (`DOCK_BERTHED`, `LOADING_STARTED`, `LOADING_FINISHED`, `WEIGHED`). If gate-out delay is caused by security/weighbridge congestion after loading is finished, that duration is recorded as separate "Plant Exit Dwell" for transparent reconciliation.

---

## 4. Multi-Tenant Cross-Access for Bookings & Shipments

### Ambiguity
- In a multi-tenant platform, a shipment is created and owned by a Shipper tenant, but must be viewed and updated (e.g., driver nomination, transit status) by a Transporter tenant. How is this securely achieved without violating tenant data isolation?

### Battle-Tested Default
CargoPulse implements **Relational Dual-Tenant Authorization**:
- The `shipments` table is strictly owned by `tenant_id` (the Shipper).
- The `bookings` table explicitly binds `shipment_id`, `shipper_tenant_id`, and `transporter_tenant_id`.
- Data access layers enforce:
  $$\text{Access Granted} \iff (\text{SessionTenant} = \text{shipments.tenant\_id}) \lor (\exists \text{ booking}: \text{booking.transporter\_tenant\_id} = \text{SessionTenant})$$
- Transporter queries are restricted to a filtered view that omits internal shipper notes, commercial purchase order numbers, and other carriers' bids.

---

## 5. Telematics Data Volume & Storage Partitioning

### Ambiguity
- High-frequency GPS telemetry (e.g., coordinates every 30 seconds for 5,000 active trucks) produces millions of rows weekly. Storing this in a standard unpartitioned PostgreSQL table risks table bloat, slow indexing, and degraded query performance.

### Battle-Tested Default
1. **PostgreSQL Native Range Partitioning**:
   The `telemetry_logs` table is partitioned by range on `recorded_at` into **monthly partitions** (e.g., `telemetry_logs_2026_11`, `telemetry_logs_2026_12`).
2. **Hot vs. Cold Separation**:
   - **Hot Telematics (Last Known Location)**: Cached in Redis geospatial index (`GEOADD / GEORADIUS`) for sub-millisecond dashboard and map queries.
   - **Historical Breadcrumbs**: Inserted in micro-batches (via Celery buffer every 10 seconds) into PostgreSQL partition tables.
   - **Automated Archival**: Partitions older than 90 days are compressed and archived to cold S3/Parquet storage.

---

## 6. Discrepancy Tolerance Thresholds in Freight Audit

### Ambiguity
- What constitutes an acceptable invoice discrepancy versus an automated dispute during three-way reconciliation?

### Battle-Tested Default
Configurable per-shipper tolerance rules with standard enterprise defaults:
- **Absolute Variance Threshold**: Discrepancies $\le \$5.00$ (or regional equivalent) due to fractional toll rounding or fuel index decimals are automatically rounded and marked `AUTO_MATCHED`.
- **Percentage Variance Threshold**: Discrepancies $\le 0.5\%$ of base freight are routed to a quick 1-click approval queue.
- **Detention Variance**: Claimed detention hours exceeding verified gate log hours by $> 15\text{ minutes}$ are automatically trimmed to the gate log record with an automated line-item explanation sent to the carrier.
- **Disputed Amounts**: Any invoice exceeding tolerance is flagged as `DISPUTED` and cannot generate an ERP payment voucher until a mutual adjustment (Credit/Debit note) is accepted by both parties.
