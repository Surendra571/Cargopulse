# Business Workflows

## 1. End-to-End Shipment Lifecycle

1. **Creation**: Manufacturer ops creates a shipment (`DRAFT` -> `READY_FOR_MATCHING`) with origin, destination, cargo weight/type, and pickup/delivery SLA windows.
2. **Transporter Matching**: Intelligent matching scores approved carriers on lane experience, on-time SLA reliability, and active capacity.
3. **Booking & Commitment**: Dispatcher books a transporter (`PENDING_CONFIRMATION` -> `CONFIRMED`), creating a `PickupCommitment` (`COMMITTED`).
4. **Pickup Execution**: Carrier updates pickup to `STARTED` and `COMPLETED`; shipment moves to `IN_TRANSIT`.
5. **Tracking & e-POD**: Telemetry milestones track transit until `DELIVERED`, followed by digital Proof of Delivery (`POD`) upload and verification.
6. **Freight Reconciliation**: Verified e-PODs and contracted rates are matched in the Reconciliation Center (`MATCHED` / `DISPUTED` / `APPROVED`).

## 2. Missed Pickup Recovery Workflow

- If a `PickupCommitment` breaches its pickup window without `STARTED`/`COMPLETED`, it transitions to `MISSED`, opens an `ExceptionRecord`, and surfaces in the **Missed Pickup Recovery Center** (`/recovery`).
- Dispatchers can reassign an alternate transporter, reschedule the pickup window, or escalate directly.

## 3. Approval-Gated AI Coordinator Workflow

1. Operator asks the AI Coordinator (`/ai-coordinator`) to diagnose delays, summarize exceptions, or suggest recovery actions.
2. When an operational mutation is recommended, the AI creates an **Action Proposal** (`PENDING_APPROVAL`) instead of mutating state directly.
3. Only after an authorized user clicks **Approve** does the backend execute the action and record the decision in `audit_logs`.
