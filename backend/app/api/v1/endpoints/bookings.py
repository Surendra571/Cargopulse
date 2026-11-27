import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.enums import BookingStatus
from app.schemas.booking import (
    BookingAcceptRequest,
    BookingAssignResourceRequest,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingDetailResponse,
    BookingListResponse,
    BookingRejectRequest,
    BookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter()


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking tender",
    description="Dispatch manager creates a booking tender to an eligible verified transporter.",
)
async def create_booking(
    request: Request,
    payload: BookingCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await BookingService.create_booking(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "",
    response_model=BookingListResponse,
    summary="List bookings with filters",
    description="Returns a paginated list of bookings filterable by status, shipment, or carrier.",
)
async def list_bookings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    shipment_id: Optional[uuid.UUID] = Query(default=None),
    transporter_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[BookingStatus] = Query(default=None),
    search: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingListResponse:
    return await BookingService.list_bookings(
        session=session,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        shipment_id=shipment_id,
        transporter_id=transporter_id,
        status_filter=status,
        search=search,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingDetailResponse,
    summary="Get booking details",
    description="Returns comprehensive details of a booking including milestone events and audit logs.",
)
async def get_booking_detail(
    booking_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingDetailResponse:
    return await BookingService.get_booking_detail(
        session=session,
        organization_id=current_user.organization_id,
        booking_id=booking_id,
    )


@router.post(
    "/{booking_id}/accept",
    response_model=BookingResponse,
    summary="Accept booking tender",
    description="Transporter reviews and accepts a booking request. Can optionally provide vehicle & driver to confirm dispatch immediately.",
)
async def accept_booking(
    booking_id: uuid.UUID,
    request: Request,
    payload: BookingAcceptRequest = BookingAcceptRequest(),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await BookingService.accept_booking(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        booking_id=booking_id,
        data=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/{booking_id}/reject",
    response_model=BookingResponse,
    summary="Reject booking tender",
    description="Transporter rejects a booking request with operational justification.",
)
async def reject_booking(
    booking_id: uuid.UUID,
    request: Request,
    payload: BookingRejectRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await BookingService.reject_booking(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        booking_id=booking_id,
        data=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/{booking_id}/assign",
    response_model=BookingResponse,
    summary="Assign vehicle and driver to booking",
    description="Supplies vehicle and driver allocations for an accepted booking. Validates eligibility and transitions booking to CONFIRMED.",
)
async def assign_resources(
    booking_id: uuid.UUID,
    request: Request,
    payload: BookingAssignResourceRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await BookingService.assign_resources(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        booking_id=booking_id,
        data=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel booking tender",
    description="Cancels an active or pending booking tender and releases the shipment.",
)
async def cancel_booking(
    booking_id: uuid.UUID,
    request: Request,
    payload: BookingCancelRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await BookingService.cancel_booking(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        booking_id=booking_id,
        data=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/maintenance/expire-overdue",
    summary="Expire overdue bookings",
    description="Operational maintenance endpoint to scan and expire past-due tender requests.",
)
async def expire_overdue_bookings(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    count = await BookingService.expire_overdue_bookings(
        session=session,
        organization_id=current_user.organization_id,
    )
    return {"success": True, "expired_count": count}
