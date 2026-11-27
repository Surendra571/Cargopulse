import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.matching import (
    TransporterMatchingResponse,
    TransporterSelectionRequest,
    TransporterSelectionResponse,
)
from app.services.matching_service import MatchingService

router = APIRouter(tags=["Intelligent Matching"])


@router.get(
    "/shipments/{shipment_id}/match",
    response_model=TransporterMatchingResponse,
    summary="Recommend and Rank Eligible Transporters for a Shipment",
)
async def match_transporters_for_shipment(
    shipment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterMatchingResponse:
    """
    Executes algorithmic matching for a specific shipment:
    1. Evaluates Hard Eligibility Filters:
       - Carrier verification status (VERIFIED only)
       - Account active status (non-suspended)
       - Route coverage (dedicated corridor, operating routes, or service regions)
       - Vehicle capacity & equipment type compatibility
       - Non-expired documentation (insurance & fitness certificates)
    2. Computes an explainable scorecard:
       - Pickup Reliability (40%)
       - On-Time Delivery (25%)
       - Booking Acceptance (15%)
       - Route Suitability (10%)
       - Cost Competitiveness (10%)
    3. Normalizes and handles new carriers without historical data.
    4. Logs recommendation run into AIActionRecord for auditable operational tracking.
    """
    return await MatchingService.match_transporters_for_shipment(
        session=db,
        organization_id=current_user.organization_id,
        shipment_id=shipment_id,
    )


@router.post(
    "/shipments/{shipment_id}/match/select",
    response_model=TransporterSelectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Dispatch Manager Manual Selection of Recommended Transporter",
)
async def select_transporter(
    shipment_id: uuid.UUID,
    data: TransporterSelectionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransporterSelectionResponse:
    """
    Allows an authorized dispatch manager or operations lead to manually select
    a transporter for a shipment.
    Creates a TransporterBooking tender, updates shipment assignment, logs
    shipment event milestone, and updates the AIActionRecord.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    return await MatchingService.select_transporter_for_shipment(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        shipment_id=shipment_id,
        data=data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
