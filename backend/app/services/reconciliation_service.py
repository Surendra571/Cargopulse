"""
CargoPulse Phase 17: Reconciliation Service & Comparison Engine
Compares planned commitments with actual execution across the 6 core categories:
1. Pickup time (Scheduled vs Actual)
2. Delivery time (Expected vs Actual)
3. Shipment quantity (Manifest expected vs POD received)
4. Booking vs Actual Transporter (Tendered vs Actual executing carrier)
5. POD Completeness (Required signature/photos vs Submitted evidence)
6. Freight charges (Agreed rate vs Billed invoice charges)
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shipment import Shipment, ShipmentEvent, TransporterBooking, PickupCommitment, ShipmentAssignment
from app.models.transporter import Transporter
from app.models.operations import (
    ReconciliationRecord,
    LogisticsReconciliationItem,
    ProofOfDelivery,
    DeliveryDiscrepancy,
    ExceptionRecord
)
from app.models.integrations import AuditLog
from app.models.enums import (
    ReconciliationStatus,
    ReconciliationCategory,
    DiscrepancyItemStatus,
    BookingStatus,
    ShipmentStatus
)


class ReconciliationService:
    """
    Core engine that executes planned vs actual comparisons without altering
    original commitment records.
    """

    @classmethod
    async def reconcile_shipment(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        organization_id: uuid.UUID,
        trigger_user_id: Optional[uuid.UUID] = None
    ) -> Tuple[ReconciliationRecord, List[LogisticsReconciliationItem]]:
        """
        Executes comparison across all 6 categories and persists discrepancy items.
        """
        # 1. Retrieve shipment
        ship_res = await session.execute(
            select(Shipment).where(
                Shipment.id == shipment_id,
                Shipment.organization_id == organization_id,
                Shipment.is_deleted == False
            )
        )
        shipment = ship_res.scalar_one_or_none()
        if not shipment:
            raise ValueError(f"Shipment '{shipment_id}' not found.")

        # 2. Retrieve original & latest booking
        bk_res = await session.execute(
            select(TransporterBooking).options(selectinload(TransporterBooking.transporter)).where(
                TransporterBooking.shipment_id == shipment_id
            ).order_by(TransporterBooking.created_at.asc())
        )
        bookings = bk_res.scalars().all()
        confirmed_booking = next((b for b in reversed(bookings) if b.status in [BookingStatus.CONFIRMED, BookingStatus.ACCEPTED]), None)
        original_booking = bookings[0] if bookings else None

        # 3. Retrieve assignment history
        asgn_res = await session.execute(
            select(ShipmentAssignment).options(
                selectinload(ShipmentAssignment.vehicle),
                selectinload(ShipmentAssignment.driver)
            ).where(
                ShipmentAssignment.shipment_id == shipment_id
            ).order_by(ShipmentAssignment.created_at.desc())
        )
        assignments = asgn_res.scalars().all()
        active_assignment = next((a for a in assignments if a.status.value in ["ASSIGNED", "ACCEPTED"]), None)

        # 4. Retrieve shipment events
        ev_res = await session.execute(
            select(ShipmentEvent).where(
                ShipmentEvent.shipment_id == shipment_id
            ).order_by(ShipmentEvent.occurred_at.asc())
        )
        events = ev_res.scalars().all()

        # 5. Retrieve POD
        pod_res = await session.execute(
            select(ProofOfDelivery).options(selectinload(ProofOfDelivery.discrepancies)).where(
                ProofOfDelivery.shipment_id == shipment_id
            )
        )
        pod = pod_res.scalar_one_or_none()

        # 6. Retrieve pickup commitment
        commit_res = await session.execute(
            select(PickupCommitment).where(
                PickupCommitment.shipment_id == shipment_id
            ).order_by(PickupCommitment.created_at.desc())
        )
        commitment = commit_res.scalars().first()

        # Primary transporter identity
        primary_transporter_id = None
        if confirmed_booking:
            primary_transporter_id = confirmed_booking.transporter_id
        elif active_assignment and active_assignment.vehicle:
            primary_transporter_id = active_assignment.vehicle.transporter_id
        elif original_booking:
            primary_transporter_id = original_booking.transporter_id
        else:
            # Fallback to first transporter in org if none assigned yet
            t_fallback = await session.execute(select(Transporter.id).where(Transporter.organization_id == organization_id).limit(1))
            primary_transporter_id = t_fallback.scalar_one_or_none() or uuid.uuid4()

        # Check or create parent ReconciliationRecord
        rec_res = await session.execute(
            select(ReconciliationRecord).where(ReconciliationRecord.shipment_id == shipment_id)
        )
        reconciliation = rec_res.scalar_one_or_none()
        if not reconciliation:
            base_rate = float(confirmed_booking.agreed_rate or confirmed_booking.offered_rate or 1000.0) if confirmed_booking else 1000.0
            reconciliation = ReconciliationRecord(
                id=uuid.uuid4(),
                organization_id=organization_id,
                shipment_id=shipment_id,
                transporter_id=primary_transporter_id,
                base_freight_charge=base_rate,
                toll_charges=0.0,
                detention_charges=0.0,
                penalties_deducted=0.0,
                discrepancy_deductions=0.0,
                final_payable_amount=base_rate,
                status=ReconciliationStatus.PENDING,
                invoice_number=shipment.invoice_number
            )
            session.add(reconciliation)
            await session.flush()

        # Clear existing unassigned items for fresh comparison
        existing_items_res = await session.execute(
            select(LogisticsReconciliationItem).where(
                LogisticsReconciliationItem.shipment_id == shipment_id,
                LogisticsReconciliationItem.status == "OPEN"
            )
        )
        for old_item in existing_items_res.scalars().all():
            await session.delete(old_item)

        items: List[LogisticsReconciliationItem] = []

        # -------------------------------------------------------------
        # Category 1: Pickup Time Comparison
        # -------------------------------------------------------------
        expected_pickup = commitment.pickup_deadline if commitment and commitment.pickup_deadline else shipment.scheduled_pickup_time
        actual_pickup = shipment.actual_pickup_time
        pickup_is_missing = actual_pickup is None
        pickup_matched = False
        pickup_delta = None

        if pickup_is_missing:
            # Check if overdue
            if datetime.now(timezone.utc) > expected_pickup:
                diff_min = int((datetime.now(timezone.utc) - expected_pickup).total_seconds() / 60)
                pickup_delta = f"Overdue by {diff_min} mins (Not picked up)"
                severity = "HIGH" if diff_min > 60 else "MEDIUM"
            else:
                pickup_delta = "Pending scheduled pickup window"
                severity = "LOW"
        else:
            diff_min = int((actual_pickup - expected_pickup).total_seconds() / 60)
            if diff_min <= 15:  # 15 minute grace period
                pickup_matched = True
                pickup_delta = f"On time ({diff_min} mins variance)"
                severity = "LOW"
            else:
                pickup_matched = False
                pickup_delta = f"Delayed by {diff_min} mins"
                severity = "HIGH" if diff_min > 120 else "MEDIUM"

        items.append(LogisticsReconciliationItem(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            reconciliation_id=reconciliation.id,
            category=ReconciliationCategory.PICKUP_TIME.value,
            status="RESOLVED" if pickup_matched else "OPEN",
            expected_value=expected_pickup.isoformat() if expected_pickup else None,
            actual_value=actual_pickup.isoformat() if actual_pickup else None,
            discrepancy_delta=pickup_delta,
            severity=severity,
            is_matched=pickup_matched,
            is_missing_data=pickup_is_missing,
            item_metadata={"diff_minutes": diff_min if not pickup_is_missing else None}
        ))

        # -------------------------------------------------------------
        # Category 2: Delivery Time Comparison
        # -------------------------------------------------------------
        expected_delivery = shipment.expected_delivery_time
        actual_delivery = shipment.actual_delivery_time or (pod.signed_at if pod else None)
        delivery_is_missing = actual_delivery is None
        delivery_matched = False
        delivery_delta = None

        if delivery_is_missing:
            if datetime.now(timezone.utc) > expected_delivery:
                del_diff = int((datetime.now(timezone.utc) - expected_delivery).total_seconds() / 60)
                delivery_delta = f"Overdue by {del_diff} mins"
                severity = "HIGH"
            else:
                delivery_delta = "In-transit (pending delivery)"
                severity = "LOW"
        else:
            del_diff = int((actual_delivery - expected_delivery).total_seconds() / 60)
            if del_diff <= 30:  # 30 minute grace window
                delivery_matched = True
                delivery_delta = f"On time ({del_diff} mins variance)"
                severity = "LOW"
            else:
                delivery_matched = False
                delivery_delta = f"Delayed delivery by {del_diff} mins"
                severity = "HIGH" if del_diff > 240 else "MEDIUM"

        items.append(LogisticsReconciliationItem(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            reconciliation_id=reconciliation.id,
            category=ReconciliationCategory.DELIVERY_TIME.value,
            status="RESOLVED" if delivery_matched else "OPEN",
            expected_value=expected_delivery.isoformat() if expected_delivery else None,
            actual_value=actual_delivery.isoformat() if actual_delivery else None,
            discrepancy_delta=delivery_delta,
            severity=severity,
            is_matched=delivery_matched,
            is_missing_data=delivery_is_missing,
            item_metadata={"diff_minutes": del_diff if not delivery_is_missing else None}
        ))

        # -------------------------------------------------------------
        # Category 3: Shipment Quantity Comparison
        # -------------------------------------------------------------
        expected_qty = shipment.package_count
        received_qty = pod.received_quantity if pod else None
        qty_is_missing = received_qty is None
        qty_matched = False
        qty_delta = None

        if qty_is_missing:
            qty_delta = "POD not submitted yet"
            severity = "MEDIUM"
        else:
            diff_qty = received_qty - expected_qty
            if diff_qty == 0:
                qty_matched = True
                qty_delta = "100% Quantity Matched (0 unit variance)"
                severity = "LOW"
            elif diff_qty < 0:
                qty_matched = False
                qty_delta = f"Shortage of {abs(diff_qty)} packages"
                severity = "CRITICAL" if abs(diff_qty) > 5 else "HIGH"
            else:
                qty_matched = False
                qty_delta = f"Overage of {diff_qty} packages"
                severity = "MEDIUM"

        items.append(LogisticsReconciliationItem(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            reconciliation_id=reconciliation.id,
            category=ReconciliationCategory.SHIPMENT_QUANTITY.value,
            status="RESOLVED" if qty_matched else "OPEN",
            expected_value=str(expected_qty),
            actual_value=str(received_qty) if not qty_is_missing else None,
            discrepancy_delta=qty_delta,
            severity=severity,
            is_matched=qty_matched,
            is_missing_data=qty_is_missing,
            item_metadata={"expected": expected_qty, "received": received_qty}
        ))

        # -------------------------------------------------------------
        # Category 4: Booking versus Actual Transporter
        # -------------------------------------------------------------
        booked_transporter_id = original_booking.transporter_id if original_booking else None
        booked_name = original_booking.transporter.name if original_booking and original_booking.transporter else "None"
        
        actual_transporter_id = None
        actual_name = "Unassigned"
        if confirmed_booking and confirmed_booking.transporter:
            actual_transporter_id = confirmed_booking.transporter_id
            actual_name = confirmed_booking.transporter.name
        elif active_assignment and active_assignment.vehicle:
            actual_transporter_id = active_assignment.vehicle.transporter_id
            t_act = await session.execute(select(Transporter.name).where(Transporter.id == actual_transporter_id))
            actual_name = t_act.scalar_one_or_none() or "Carrier"

        carrier_missing = actual_transporter_id is None
        carrier_matched = False
        carrier_delta = None

        if carrier_missing:
            carrier_delta = "No executing transporter recorded"
            severity = "HIGH"
        elif booked_transporter_id and actual_transporter_id != booked_transporter_id:
            carrier_matched = False
            carrier_delta = f"Transporter Reassigned (Planned: {booked_name} -> Actual: {actual_name})"
            severity = "MEDIUM"
        else:
            carrier_matched = True
            carrier_delta = f"Matched carrier: {actual_name}"
            severity = "LOW"

        items.append(LogisticsReconciliationItem(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            reconciliation_id=reconciliation.id,
            category=ReconciliationCategory.BOOKING_VS_ACTUAL_TRANSPORTER.value,
            status="RESOLVED" if carrier_matched else "OPEN",
            expected_value=booked_name,
            actual_value=actual_name,
            discrepancy_delta=carrier_delta,
            severity=severity,
            is_matched=carrier_matched,
            is_missing_data=carrier_missing,
            item_metadata={"booked_id": str(booked_transporter_id) if booked_transporter_id else None, "actual_id": str(actual_transporter_id) if actual_transporter_id else None}
        ))

        # -------------------------------------------------------------
        # Category 5: POD Completeness Comparison
        # -------------------------------------------------------------
        pod_missing = pod is None
        pod_matched = False
        pod_delta = None

        if pod_missing:
            pod_delta = "No POD record found"
            severity = "HIGH"
        else:
            missing_elements = []
            if not pod.signature_image_url and not pod.document_url:
                missing_elements.append("Recipient Signature / Document")
            if not pod.delivery_photo_urls or len(pod.delivery_photo_urls) == 0:
                missing_elements.append("Delivery Photographs")
            if not pod.signed_by_name:
                missing_elements.append("Recipient Identity")

            if not missing_elements:
                pod_matched = True
                pod_delta = "Complete Proof of Delivery verified"
                severity = "LOW"
            else:
                pod_matched = False
                pod_delta = f"Incomplete POD: missing {', '.join(missing_elements)}"
                severity = "HIGH"

        items.append(LogisticsReconciliationItem(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            reconciliation_id=reconciliation.id,
            category=ReconciliationCategory.POD_COMPLETENESS.value,
            status="RESOLVED" if pod_matched else "OPEN",
            expected_value="Signature, Photos, Recipient Name",
            actual_value=f"Signature={bool(pod and (pod.signature_image_url or pod.document_url))}, Photos={len(pod.delivery_photo_urls) if pod and pod.delivery_photo_urls else 0}" if pod else "None",
            discrepancy_delta=pod_delta,
            severity=severity,
            is_matched=pod_matched,
            is_missing_data=pod_missing,
            item_metadata={"pod_id": str(pod.id) if pod else None}
        ))

        # -------------------------------------------------------------
        # Category 6: Freight Charge Discrepancies
        # -------------------------------------------------------------
        agreed_rate = float(confirmed_booking.agreed_rate or confirmed_booking.offered_rate or 0.0) if confirmed_booking else float(reconciliation.base_freight_charge)
        billed_rate = float(reconciliation.final_payable_amount) if reconciliation.final_payable_amount else agreed_rate
        invoiced_diff = billed_rate - agreed_rate
        charge_missing = False
        charge_matched = abs(invoiced_diff) < 0.01
        charge_delta = None

        if charge_matched:
            charge_delta = f"Charges match agreed rate (${agreed_rate:.2f})"
            severity = "LOW"
        elif invoiced_diff > 0:
            charge_delta = f"Overcharge: billed ${billed_rate:.2f} vs agreed ${agreed_rate:.2f} (+${invoiced_diff:.2f})"
            severity = "HIGH"
        else:
            charge_delta = f"Undercharge/Deduction: billed ${billed_rate:.2f} vs agreed ${agreed_rate:.2f} (-${abs(invoiced_diff):.2f})"
            severity = "MEDIUM"

        items.append(LogisticsReconciliationItem(
            id=uuid.uuid4(),
            organization_id=organization_id,
            shipment_id=shipment_id,
            reconciliation_id=reconciliation.id,
            category=ReconciliationCategory.FREIGHT_CHARGES.value,
            status="RESOLVED" if charge_matched else "OPEN",
            expected_value=f"${agreed_rate:.2f}",
            actual_value=f"${billed_rate:.2f}",
            discrepancy_delta=charge_delta,
            severity=severity,
            is_matched=charge_matched,
            is_missing_data=charge_missing,
            item_metadata={"agreed_rate": agreed_rate, "billed_rate": billed_rate, "variance": invoiced_diff}
        ))

        # Persist items
        for it in items:
            session.add(it)

        # Update parent reconciliation statistics
        total_disc = sum(1 for it in items if not it.is_matched)
        has_missing = any(it.is_missing_data for it in items)
        has_mismatch = any((not it.is_matched and not it.is_missing_data) for it in items)

        reconciliation.total_discrepancies = total_disc
        reconciliation.has_mismatches = has_mismatch
        reconciliation.has_missing_data = has_missing

        if total_disc == 0:
            reconciliation.status = ReconciliationStatus.MATCHED
        elif reconciliation.status != ReconciliationStatus.CLOSED:
            reconciliation.status = ReconciliationStatus.DISCREPANCY

        reconciliation.summary_data = {
            "pickup_matched": pickup_matched,
            "delivery_matched": delivery_matched,
            "quantity_matched": qty_matched,
            "carrier_matched": carrier_matched,
            "pod_matched": pod_matched,
            "charges_matched": charge_matched,
            "reconciled_at": datetime.now(timezone.utc).isoformat()
        }

        # Log audit
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=trigger_user_id,
            action="SHIPMENT_RECONCILIATION_EVALUATED",
            entity_name="ReconciliationRecord",
            entity_id=reconciliation.id,
            changes={
                "shipment_id": str(shipment_id),
                "total_discrepancies": total_disc,
                "has_missing_data": has_missing,
                "has_mismatches": has_mismatch,
                "status": reconciliation.status.value
            }
        )
        session.add(audit)

        await session.commit()
        await session.refresh(reconciliation)

        return reconciliation, items

    @classmethod
    async def list_reconciliations(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        status_filter: Optional[str] = None,
        has_discrepancy_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List reconciliation summaries with shipment and carrier information.
        """
        query = select(ReconciliationRecord).options(
            selectinload(ReconciliationRecord.shipment)
        ).where(
            ReconciliationRecord.organization_id == organization_id,
            ReconciliationRecord.is_deleted == False
        )

        if status_filter:
            try:
                st_enum = ReconciliationStatus[status_filter.upper()]
                query = query.where(ReconciliationRecord.status == st_enum)
            except KeyError:
                pass

        if has_discrepancy_only:
            query = query.where(ReconciliationRecord.total_discrepancies > 0)

        query = query.order_by(desc(ReconciliationRecord.updated_at)).limit(limit)
        res = await session.execute(query)
        records = res.scalars().all()

        results = []
        for r in records:
            # Transporter name lookup
            t_res = await session.execute(
                select(Transporter.name).where(Transporter.id == r.transporter_id)
            )
            t_name = t_res.scalar_one_or_none()

            results.append({
                "id": str(r.id),
                "organization_id": str(r.organization_id),
                "shipment_id": str(r.shipment_id),
                "tracking_number": r.shipment.tracking_number if r.shipment else None,
                "transporter_id": str(r.transporter_id),
                "transporter_name": t_name or "Carrier",
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "base_freight_charge": float(r.base_freight_charge),
                "final_payable_amount": float(r.final_payable_amount),
                "total_discrepancies": r.total_discrepancies,
                "resolved_discrepancies": r.resolved_discrepancies,
                "has_mismatches": r.has_mismatches,
                "has_missing_data": r.has_missing_data,
                "invoice_number": r.invoice_number,
                "created_at": r.created_at,
                "updated_at": r.updated_at
            })

        return results

    @classmethod
    async def get_reconciliation_detail(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        organization_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Retrieves detailed comparison and all 6 category items.
        If no record exists, triggers reconciliation comparison on the fly.
        """
        rec_res = await session.execute(
            select(ReconciliationRecord).options(
                selectinload(ReconciliationRecord.shipment),
                selectinload(ReconciliationRecord.items)
            ).where(
                ReconciliationRecord.shipment_id == shipment_id,
                ReconciliationRecord.organization_id == organization_id
            )
        )
        rec = rec_res.scalar_one_or_none()

        if not rec or not rec.items:
            await cls.reconcile_shipment(session, shipment_id, organization_id)
            rec_res = await session.execute(
                select(ReconciliationRecord).options(
                    selectinload(ReconciliationRecord.shipment),
                    selectinload(ReconciliationRecord.items)
                ).where(
                    ReconciliationRecord.shipment_id == shipment_id,
                    ReconciliationRecord.organization_id == organization_id
                )
            )
            rec = rec_res.scalar_one()
            items = rec.items
        else:
            items = rec.items

        t_res = await session.execute(
            select(Transporter.name).where(Transporter.id == rec.transporter_id)
        )
        t_name = t_res.scalar_one_or_none()

        # Fetch recent audit logs for reconciliation
        audit_res = await session.execute(
            select(AuditLog).where(
                AuditLog.entity_name == "ReconciliationRecord",
                AuditLog.entity_id == rec.id
            ).order_by(desc(AuditLog.created_at)).limit(10)
        )
        audit_logs = [
            {
                "id": str(a.id),
                "action": a.action,
                "changes": a.changes,
                "created_at": a.created_at.isoformat()
            }
            for a in audit_res.scalars().all()
        ]

        shipment = rec.shipment
        shipment_summary = {
            "id": str(shipment.id),
            "tracking_number": shipment.tracking_number,
            "status": shipment.status.value if hasattr(shipment.status, "value") else str(shipment.status),
            "origin": f"{shipment.origin_city}, {shipment.origin_state}",
            "destination": f"{shipment.destination_city}, {shipment.destination_state}",
            "scheduled_pickup": shipment.scheduled_pickup_time.isoformat(),
            "expected_delivery": shipment.expected_delivery_time.isoformat(),
            "actual_pickup": shipment.actual_pickup_time.isoformat() if shipment.actual_pickup_time else None,
            "actual_delivery": shipment.actual_delivery_time.isoformat() if shipment.actual_delivery_time else None,
            "package_count": shipment.package_count,
            "weight_kg": float(shipment.total_weight_kg)
        }

        rec_summary = {
            "id": str(rec.id),
            "organization_id": str(rec.organization_id),
            "shipment_id": str(rec.shipment_id),
            "tracking_number": shipment.tracking_number,
            "transporter_id": str(rec.transporter_id),
            "transporter_name": t_name or "Carrier",
            "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
            "base_freight_charge": float(rec.base_freight_charge),
            "final_payable_amount": float(rec.final_payable_amount),
            "total_discrepancies": rec.total_discrepancies,
            "resolved_discrepancies": rec.resolved_discrepancies,
            "has_mismatches": rec.has_mismatches,
            "has_missing_data": rec.has_missing_data,
            "invoice_number": rec.invoice_number,
            "created_at": rec.created_at,
            "updated_at": rec.updated_at
        }

        return {
            "reconciliation": rec_summary,
            "shipment_summary": shipment_summary,
            "items": [
                {
                    "id": str(it.id),
                    "organization_id": str(it.organization_id),
                    "shipment_id": str(it.shipment_id),
                    "reconciliation_id": str(it.reconciliation_id) if it.reconciliation_id else None,
                    "category": it.category,
                    "status": it.status,
                    "expected_value": it.expected_value,
                    "actual_value": it.actual_value,
                    "discrepancy_delta": it.discrepancy_delta,
                    "severity": it.severity,
                    "is_matched": it.is_matched,
                    "is_missing_data": it.is_missing_data,
                    "assigned_user_id": str(it.assigned_user_id) if it.assigned_user_id else None,
                    "investigation_notes": it.investigation_notes,
                    "resolution_notes": it.resolution_notes,
                    "resolved_by_user_id": str(it.resolved_by_user_id) if it.resolved_by_user_id else None,
                    "resolved_at": it.resolved_at,
                    "closed_at": it.closed_at,
                    "item_metadata": it.item_metadata,
                    "created_at": it.created_at,
                    "updated_at": it.updated_at
                }
                for it in items
            ],
            "audit_history": audit_logs
        }

    @classmethod
    async def update_discrepancy_item(
        cls,
        session: AsyncSession,
        item_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        assigned_user_id: Optional[uuid.UUID] = None,
        investigation_notes: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        status: Optional[str] = None
    ) -> LogisticsReconciliationItem:
        """
        Updates investigation notes, assigns discrepancy owner, and records resolution.
        """
        query = select(LogisticsReconciliationItem).where(
            LogisticsReconciliationItem.id == item_id,
            LogisticsReconciliationItem.organization_id == organization_id
        )
        res = await session.execute(query)
        item = res.scalar_one_or_none()
        if not item:
            raise ValueError(f"Reconciliation item '{item_id}' not found.")

        now = datetime.now(timezone.utc)
        if assigned_user_id:
            item.assigned_user_id = assigned_user_id
        if investigation_notes:
            item.investigation_notes = investigation_notes
            if item.status == "OPEN":
                item.status = "INVESTIGATING"
        if resolution_notes:
            item.resolution_notes = resolution_notes
            item.resolved_by_user_id = user_id
            item.resolved_at = now
            item.status = "RESOLVED"
        if status:
            item.status = status.upper()
            if item.status in ["RESOLVED", "CLOSED"]:
                item.resolved_by_user_id = user_id
                item.resolved_at = now

        # Update parent record resolved count
        if item.reconciliation_id:
            parent_res = await session.execute(
                select(ReconciliationRecord).where(ReconciliationRecord.id == item.reconciliation_id)
            )
            parent = parent_res.scalar_one_or_none()
            if parent:
                all_items_res = await session.execute(
                    select(LogisticsReconciliationItem).where(
                        LogisticsReconciliationItem.reconciliation_id == parent.id
                    )
                )
                all_items = all_items_res.scalars().all()
                resolved_count = sum(1 for it in all_items if it.status in ["RESOLVED", "CLOSED"])
                parent.resolved_discrepancies = resolved_count
                if resolved_count == len(all_items) and parent.status != ReconciliationStatus.CLOSED:
                    parent.status = ReconciliationStatus.RESOLVED

        # Log audit
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="RECONCILIATION_ITEM_UPDATED",
            entity_name="LogisticsReconciliationItem",
            entity_id=item.id,
            changes={
                "category": item.category,
                "status": item.status,
                "assigned_user_id": str(item.assigned_user_id) if item.assigned_user_id else None,
                "resolution_notes": resolution_notes
            }
        )
        session.add(audit)
        await session.commit()
        await session.refresh(item)
        return item

    @classmethod
    async def close_reconciliation(
        cls,
        session: AsyncSession,
        shipment_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        closure_notes: Optional[str] = None
    ) -> ReconciliationRecord:
        """
        Closes a reconciliation record once all discrepancies have been investigated or resolved.
        """
        rec_res = await session.execute(
            select(ReconciliationRecord).where(
                ReconciliationRecord.shipment_id == shipment_id,
                ReconciliationRecord.organization_id == organization_id
            )
        )
        rec = rec_res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Reconciliation record for shipment '{shipment_id}' not found.")

        now = datetime.now(timezone.utc)
        rec.status = ReconciliationStatus.CLOSED
        rec.closed_by_user_id = user_id
        rec.closed_at = now
        rec.resolution_notes = closure_notes

        # Close all associated items
        items_res = await session.execute(
            select(LogisticsReconciliationItem).where(
                LogisticsReconciliationItem.reconciliation_id == rec.id
            )
        )
        for it in items_res.scalars().all():
            it.status = "CLOSED"
            it.closed_at = now

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="RECONCILIATION_CLOSED",
            entity_name="ReconciliationRecord",
            entity_id=rec.id,
            changes={"status": "CLOSED", "closure_notes": closure_notes}
        )
        session.add(audit)
        await session.commit()
        await session.refresh(rec)
        return rec
