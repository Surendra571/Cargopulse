"""
CargoPulse Phase 17: Reconciliation Center REST Endpoints
Provides listing, shipment-level comparison, discrepancy assignment/investigation,
resolution, closure, and CSV/JSON export.
"""
import csv
import io
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.reconciliation import (
    ReconciliationRecordSummary,
    ReconciliationDetailResponse,
    ReconciliationItemResponse,
    UpdateDiscrepancyItemRequest,
    CloseReconciliationRequest
)
from app.services.reconciliation_service import ReconciliationService

router = APIRouter()


@router.get("", response_model=List[ReconciliationRecordSummary])
async def list_reconciliations(
    status_filter: Optional[str] = Query(None, alias="status"),
    has_discrepancy_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List reconciliation summaries across shipments with discrepancy status and financial totals.
    """
    results = await ReconciliationService.list_reconciliations(
        session=db,
        organization_id=current_user.organization_id,
        status_filter=status_filter,
        has_discrepancy_only=has_discrepancy_only,
        limit=limit
    )
    return results


@router.get("/export")
async def export_reconciliations_csv(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export reconciliation records as CSV for audit and accounting review.
    """
    records = await ReconciliationService.list_reconciliations(
        session=db,
        organization_id=current_user.organization_id,
        status_filter=status_filter,
        limit=1000
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reconciliation ID", "Shipment ID", "Tracking Number", "Carrier Name",
        "Status", "Base Freight", "Final Payable", "Total Discrepancies",
        "Resolved Discrepancies", "Has Mismatches", "Has Missing Data", "Updated At"
    ])

    for r in records:
        writer.writerow([
            r["id"],
            r["shipment_id"],
            r["tracking_number"] or "N/A",
            r["transporter_name"] or "Carrier",
            r["status"],
            f"{r['base_freight_charge']:.2f}",
            f"{r['final_payable_amount']:.2f}",
            r["total_discrepancies"],
            r["resolved_discrepancies"],
            r["has_mismatches"],
            r["has_missing_data"],
            r["updated_at"].isoformat() if hasattr(r["updated_at"], "isoformat") else str(r["updated_at"])
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cargopulse_reconciliations.csv"}
    )


@router.get("/{shipment_id}", response_model=ReconciliationDetailResponse)
async def get_shipment_reconciliation(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve full 6-category comparison and discrepancy items for a shipment.
    """
    try:
        detail = await ReconciliationService.get_reconciliation_detail(
            session=db,
            shipment_id=shipment_id,
            organization_id=current_user.organization_id
        )
        return detail
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{shipment_id}/evaluate", response_model=ReconciliationDetailResponse)
async def trigger_reconciliation_evaluation(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger fresh comparison across all 6 logistics categories for a shipment.
    """
    try:
        await ReconciliationService.reconcile_shipment(
            session=db,
            shipment_id=shipment_id,
            organization_id=current_user.organization_id,
            trigger_user_id=current_user.id
        )
        detail = await ReconciliationService.get_reconciliation_detail(
            session=db,
            shipment_id=shipment_id,
            organization_id=current_user.organization_id
        )
        return detail
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/items/{item_id}", response_model=ReconciliationItemResponse)
async def update_discrepancy_item(
    item_id: uuid.UUID,
    payload: UpdateDiscrepancyItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign discrepancy owner, record investigation findings, or record resolution.
    """
    try:
        updated = await ReconciliationService.update_discrepancy_item(
            session=db,
            item_id=item_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            assigned_user_id=payload.assigned_user_id,
            investigation_notes=payload.investigation_notes,
            resolution_notes=payload.resolution_notes,
            status=payload.status
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{shipment_id}/close")
async def close_shipment_reconciliation(
    shipment_id: uuid.UUID,
    payload: CloseReconciliationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Close reconciliation for a shipment once all discrepancies are settled.
    """
    try:
        rec = await ReconciliationService.close_reconciliation(
            session=db,
            shipment_id=shipment_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            closure_notes=payload.closure_notes
        )
        return {"success": True, "reconciliation_id": str(rec.id), "status": "CLOSED"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
