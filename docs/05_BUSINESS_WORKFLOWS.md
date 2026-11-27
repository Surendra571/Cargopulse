# 05. Business Workflows & State Machines

This document outlines the core operational workflows and formal finite state machines (FSM) governing CargoPulse.

---

## 1. Master Shipment Lifecycle State Machine

The shipment entity progresses through a deterministic, auditable lifecycle. Every state transition is atomic, validated, and logged to the immutable audit ledger.

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Shipment Created
    DRAFT --> ALLOCATED: Transporter Matched & Tendered
    DRAFT --> CANCELLED: Cancelled by Shipper

    ALLOCATED --> COMMITTED: Transporter Confirmed & Nominated
    ALLOCATED --> ALLOCATION_FAILED: Timeout / Rejected by all
    ALLOCATION_FAILED --> ALLOCATED: Re-tender / Spot Auction

    COMMITTED --> VEHICLE_EN_ROUTE: T-2h Readiness Confirmed
    COMMITTED --> PICKUP_FAILED: Nomination SLA Breached

    VEHICLE_EN_ROUTE --> GATE_IN: Security Check-in & OTP Verified
    VEHICLE_EN_ROUTE --> PICKUP_FAILED: ETA Breached / No Show

    PICKUP_FAILED --> RECOVERY_DISPATCH: Trigger Recovery Flow
    RECOVERY_DISPATCH --> COMMITTED: Backup Truck Assigned

    GATE_IN --> LOADING: Dock Berthing & Tare Weighed
    LOADING --> DISPATCHED: Loading Complete, Gross Weighed & Gate Pass Issued
    
    DISPATCHED --> IN_TRANSIT: Departed Plant Perimeter
    IN_TRANSIT --> EXCEPTION_HOLD: Breakdown / Accident / Route Deviation
    EXCEPTION_HOLD --> IN_TRANSIT: Issue Resolved / Transshipped

    IN_TRANSIT --> ARRIVED_DESTINATION: Geofence Entry at Consignee
    ARRIVED_DESTINATION --> DELIVERED: Unloaded & POD Uploaded
    
    DELIVERED --> POD_VERIFIED: Consignee & Shipper Verified
    POD_VERIFIED --> RECONCILED: Three-Way Match Approved
    RECONCILED --> [*]: Closed
```

### 1.1 State Transition Invariant Table

| Origin State | Permitted Destination | Triggering Event / Action | Required Pre-Conditions |
|---|---|---|---|
| `DRAFT` | `ALLOCATED` | Tender dispatched to carrier | Cargo weight, origin, destination, pickup window defined. |
| `DRAFT` | `CANCELLED` | Order cancellation | Shipment not yet tendered or committed. |
| `ALLOCATED` | `COMMITTED` | Transporter accepts tender | Carrier has valid contract or accepted spot rate. |
| `ALLOCATED` | `ALLOCATION_FAILED`| Waterfall expiration | All tendered carriers declined or timed out. |
| `COMMITTED` | `VEHICLE_EN_ROUTE`| Carrier confirms driver movement | Valid vehicle RC, insurance, and driver license verified. |
| `COMMITTED` | `PICKUP_FAILED` | SLA breach timer fires | Transporter failed to confirm driver positioning by SLA cutoff. |
| `VEHICLE_EN_ROUTE` | `GATE_IN` | Gate Officer checks in vehicle | Driver provides correct 6-digit OTP; GPS confirms arrival. |
| `GATE_IN` | `LOADING` | Dock berthing recorded | Vehicle passes physical inspection; tare weight logged. |
| `LOADING` | `DISPATCHED` | Gate pass generated | Gross weight logged; e-Way Bill attached; driver verified. |
| `DISPATCHED` | `IN_TRANSIT` | Vehicle clears plant geofence | Gate-out timestamp confirmed by security scan. |
| `IN_TRANSIT` | `EXCEPTION_HOLD`| Exception reported | GPS stoppage > 60m, breakdown reported, or accident. |
| `IN_TRANSIT` | `ARRIVED_DEST` | Geofence entry at consignee | GPS coordinate enters consignee radius ($\le 300\text{m}$). |
| `ARRIVED_DEST`| `DELIVERED` | Unloading complete | Driver uploads e-POD photos and consignee digital signature. |
| `DELIVERED` | `POD_VERIFIED` | Shipper verifies documents | Inspection of delivery shortages/damages; hash verified. |
| `POD_VERIFIED`| `RECONCILED` | Invoice audit complete | Rate card + gate detention + net invoice matched. |

---

## 2. Transporter Matching & Tendering Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Shipper as Logistics Dispatcher
    participant Engine as Matching Engine
    participant Carrier1 as Primary Carrier (Transporter 1)
    participant Carrier2 as Secondary Carrier (Transporter 2)
    participant Celery as Timer Worker (Redis/Celery)

    Shipper->>Engine: Initiate Matching (Shipment ID, Mode=WATERFALL)
    Engine->>Engine: Query Lane Rate Cards & Performance Scores
    Engine->>Carrier1: Issue Tender (SLA: 45 Minutes)
    Engine->>Celery: Schedule Timeout Task (ETA: Now + 45m)
    
    alt Carrier 1 Accepts Within SLA
        Carrier1->>Engine: Accept Tender
        Engine->>Celery: Cancel Timeout Task
        Engine->>Carrier1: Request Vehicle & Driver Nomination (SLA: T-4 Hours)
        Engine->>Shipper: Status -> COMMITTED
    else Carrier 1 Rejects or Times Out
        Celery->>Engine: Trigger Timeout Callback
        Engine->>Carrier1: Revoke Tender (Record Decline Reason)
        Engine->>Carrier2: Cascade Tender to Next Carrier (SLA: 45m)
        Carrier2->>Engine: Accept Tender
        Engine->>Shipper: Status -> COMMITTED (Carrier 2)
    end
```

---

## 3. Pickup Accountability & Gate Operations Workflow

This workflow represents CargoPulse's foundational guarantee: eliminating "ghost trucks" and enforcing physical gate dwell tracking.

```mermaid
sequenceDiagram
    autonumber
    actor Driver as Carrier Driver
    actor Gate as Plant Security Officer
    actor System as CargoPulse Engine
    actor Planner as Shipper Dispatcher

    Note over System,Driver: T-4 Hours to Pickup Window
    System->>Driver: Automated WhatsApp / SMS: "Confirm Positioning Status"
    Driver->>System: Ping GPS Location / Confirm En Route
    
    Note over System,Driver: T-2 Hours Checkpoint
    System->>System: Evaluate Distance vs Traffic ETA
    alt ETA > Pickup Cutoff (Critical Risk)
        System->>Planner: Issue ALERT: Pickup at Risk (Delay Probable)
    end

    Note over Driver,Gate: Physical Arrival at Factory
    Driver->>Gate: Present Shipment ID / Bilty Barcode
    Gate->>System: Lookup Shipment by Barcode
    System->>Driver: Dispatch 6-Digit Dynamic OTP via SMS
    Driver->>Gate: States 6-Digit OTP
    Gate->>System: Submit OTP + Physical Checklist (RC, License, PPE)
    System->>System: Verify OTP, Log GATE_IN Event + Timestamp
    
    Note over Gate,System: Dock Loading & Weeding
    Gate->>System: Record Tare Weight & Dock Assigned
    Note over Gate: Loading Cargo...
    Gate->>System: Record Gross Weight, Attach Weight Slip Photo
    Gate->>System: Issue Digital Gate Pass (GATE_OUT Event)
    System->>Planner: Transition Shipment to IN_TRANSIT
```

---

## 4. Failed Pickup Recovery Cascade

When a transporter commits to a load but fails to place a vehicle within the guaranteed SLA window, the automated recovery cascade initiates:

```mermaid
graph TD
    A[Nomination SLA / Arrival SLA Breached] --> B[System Marks PICKUP_FAILED_CRITICAL]
    B --> C[Post Audit Event: SLA_VIOLATION_PENALTY]
    B --> D[Deduct Transporter Reliability Score]
    B --> E{AI Recovery Coordinator Triggered}
    
    E --> F[Option 1: Fast-Path Waterfall Next Transporter]
    E --> G[Option 2: Instant Spot Auction Broadcast]
    E --> H[Option 3: Dispatch Dedicated Internal Standby Truck]
    
    F --> I[Dispatcher One-Click Approval]
    G --> I
    H --> I
    I --> J[New Carrier Assigned -> Booking Regenerated]
```

---

## 5. Delivery, e-POD & Discrepancy Recording Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Driver as Carrier Driver
    actor Consignee as Consignee Receiving Clerk
    actor ShipperAuditor as Shipper Finance Auditor
    participant Core as CargoPulse Core

    Driver->>Core: Notify Arrival at Consignee (Geofence Verified)
    Note over Driver,Consignee: Cargo Unloading & Physical Inspection
    
    alt Clean Delivery (Zero Shortage / Damage)
        Consignee->>Driver: Signs Physical Challan & Mobile Screen
        Driver->>Core: Upload e-POD (Signature + Photo of Goods + Signed Paper)
        Core->>Core: Compute SHA-256 Hash of Artifacts
        Core->>Core: Log POD_SUBMITTED (Clean)
    else Delivery with Discrepancy (Damages / Shortages)
        Consignee->>Driver: Note Broken Cases / Short Quantity on LR
        Driver->>Core: Upload Photos of Damaged Cartons + Quantities
        Consignee->>Core: Digital Endorsement of Damage Slip
        Core->>Core: Flag POD_DISCREPANCY (Damages Recorded)
        Core->>ShipperAuditor: Trigger Discrepancy Alert & Debit Note Calculation
    end

    ShipperAuditor->>Core: Verify & Approve POD
    Core->>Core: Transition to RECONCILIATION_READY
```

---

## 6. Three-Way Reconciliation Workflow

```mermaid
graph LR
    subgraph Input1["1. Contract Rate Card"]
        R1[Base Freight Rate]
        R2[Free Detention Hours: 4h]
        R3[Detention Rate: $15/hr]
    end

    subgraph Input2["2. Gate Execution Logs"]
        G1[Gate In: 10:00 AM]
        G2[Gate Out: 06:00 PM]
        G3[Total Dwell: 8h]
        G4[Billable Detention: 4h]
    end

    subgraph Input3["3. Carrier Invoice"]
        I1[Claimed Freight: $500]
        I2[Claimed Detention: $60 (4h * $15)]
        I3[Total Claimed: $560]
    end

    subgraph Engine["Reconciliation Engine"]
        M[Automated 3-Way Match]
    end

    Input1 --> Engine
    Input2 --> Engine
    Input3 --> Engine

    Engine --> V{Discrepancy Check}
    V -->|Match <= $1.00| PASS[Auto-Approve Payment Voucher]
    V -->|Mismatch > Threshold| DISPUTE[Route to Freight Auditor with Dispute Diff]
```
