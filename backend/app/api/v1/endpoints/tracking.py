import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.core.websocket_manager import tracking_ws_manager
from app.models.auth import User
from app.models.enums import ShipmentMilestone, ShipmentStatus, TrackingEventSource
from app.models.shipment import (
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.schemas.tracking import (
    ShipmentTimelineResponse,
    TrackingEventCreateRequest,
    TrackingEventResponse,
    TrackingScanResponse,
    UpdateETARequest,
    WebhookTrackingEventRequest,
)
from app.services.tracking_service import tracking_service

logger = logging.getLogger("cargopulse.api.tracking")

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/shipments", response_model=Dict[str, Any])
async def list_tracked_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_stale: Optional[bool] = Query(None),
    current_milestone: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists tracked shipments for the operational monitoring console with live location,
    current milestone, delay, and tracking staleness.
    """
    query = (
        select(Shipment)
        .options(
            selectinload(Shipment.assignments).selectinload(ShipmentAssignment.vehicle),
            selectinload(Shipment.assignments).selectinload(ShipmentAssignment.driver),
            selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
        )
        .where(
            Shipment.organization_id == current_user.organization_id,
            Shipment.is_deleted == False,
        )
    )

    if status_filter:
        query = query.where(Shipment.status == status_filter)
    if is_stale is not None:
        query = query.where(Shipment.is_tracking_stale == is_stale)
    if current_milestone:
        query = query.where(Shipment.current_milestone == current_milestone)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.where(
            or_(
                Shipment.tracking_number.ilike(search_fmt),
                Shipment.origin_city.ilike(search_fmt),
                Shipment.destination_city.ilike(search_fmt),
                Shipment.last_known_location.ilike(search_fmt),
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Pagination
    query = (
        query.order_by(
            Shipment.is_tracking_stale.desc(),
            Shipment.last_tracking_event_at.desc().nullslast(),
            Shipment.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    shipments = list((await db.execute(query)).scalars().all())

    items = []
    for s in shipments:
        carrier = None
        vehicle = None
        driver = None
        if s.bookings:
            confirmed_bkg = next((b for b in s.bookings if b.status in ["CONFIRMED", "ACCEPTED"] and not b.is_deleted), None)
            if confirmed_bkg and confirmed_bkg.transporter:
                carrier = {"id": str(confirmed_bkg.transporter.id), "name": confirmed_bkg.transporter.name}
        if s.assignments:
            active = next((a for a in s.assignments if a.status in ["ASSIGNED", "ACCEPTED"] and not a.is_deleted), s.assignments[0])
            if active:
                if active.vehicle:
                    vehicle = {"license_plate": active.vehicle.license_plate}
                if active.driver:
                    driver = {"name": f"{active.driver.first_name} {active.driver.last_name}"}

        items.append({
            "id": str(s.id),
            "tracking_number": s.tracking_number,
            "status": s.status.value,
            "current_milestone": s.current_milestone,
            "origin_city": s.origin_city,
            "destination_city": s.destination_city,
            "expected_delivery_time": s.expected_delivery_time.isoformat(),
            "actual_delivery_time": s.actual_delivery_time.isoformat() if s.actual_delivery_time else None,
            "last_known_location": s.last_known_location,
            "last_known_latitude": s.last_known_latitude,
            "last_known_longitude": s.last_known_longitude,
            "last_tracking_event_at": s.last_tracking_event_at.isoformat() if s.last_tracking_event_at else None,
            "is_tracking_stale": s.is_tracking_stale,
            "eta_delay_minutes": s.eta_delay_minutes,
            "total_weight_kg": float(s.total_weight_kg),
            "carrier": carrier,
            "vehicle": vehicle,
            "driver": driver,
        })

    pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/shipments/{shipment_id}/timeline", response_model=ShipmentTimelineResponse)
async def get_shipment_timeline(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the comprehensive chronological tracking event timeline, 10-milestone roadmap,
    telematics coordinates, and carrier details for a shipment.
    """
    return await tracking_service.get_shipment_timeline(
        session=db,
        shipment_id=shipment_id,
        current_user=current_user,
    )


@router.post("/shipments/{shipment_id}/events", response_model=TrackingEventResponse)
async def record_tracking_event(
    shipment_id: uuid.UUID,
    payload: TrackingEventCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Records a real-time tracking or milestone event from an operator, carrier coordinator,
    or driver. Validates progressive state transitions and broadcasts via WebSockets.
    """
    event = await tracking_service.record_tracking_event(
        session=db,
        shipment_id=shipment_id,
        req=payload,
        current_user=current_user,
    )
    return TrackingEventResponse.model_validate(event)


@router.post("/shipments/{shipment_id}/eta", response_model=TrackingEventResponse)
async def update_shipment_eta(
    shipment_id: uuid.UUID,
    payload: UpdateETARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates the expected delivery time (ETA) based on ground transporter or operator report.
    Automatically checks for significant delay (>60m) and triggers exception triage if breached.
    """
    event = await tracking_service.update_eta(
        session=db,
        shipment_id=shipment_id,
        req=payload,
        current_user=current_user,
    )
    return TrackingEventResponse.model_validate(event)


@router.post("/scan", response_model=TrackingScanResponse)
async def trigger_stale_tracking_scan(
    threshold_hours: int = Query(6, ge=1, le=72),
    simulated_now: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes surveillance scan across all active shipments to identify stale tracking pings,
    mark is_tracking_stale, log events, and open TRACKING_STALE exceptions.
    """
    parsed_now = None
    if simulated_now:
        try:
            parsed_now = datetime.fromisoformat(simulated_now.replace(" ", "+"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid simulated_now datetime format.",
            )

    return await tracking_service.scan_stale_tracking(
        session=db,
        organization_id=current_user.organization_id,
        threshold_hours=threshold_hours,
        simulated_now=parsed_now,
    )


@router.post("/webhook", response_model=TrackingEventResponse)
async def receive_webhook_tracking_event(
    payload: WebhookTrackingEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingests external telematics and transporter webhook tracking updates.
    Resolves shipment by ID or tracking number, safely records out-of-order pings,
    and broadcasts live updates.
    """
    shipment_id = payload.shipment_id
    if not shipment_id and payload.tracking_number:
        stmt = (
            select(Shipment)
            .where(Shipment.tracking_number == payload.tracking_number)
            .order_by(Shipment.created_at.desc())
        )
        shipment = (await db.execute(stmt)).scalars().first()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shipment with tracking number {payload.tracking_number} not found."
            )
        shipment_id = shipment.id

    if not shipment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either shipment_id or tracking_number must be specified.",
        )

    create_req = TrackingEventCreateRequest(
        milestone=payload.milestone if payload.milestone in [m.value for m in ShipmentMilestone] else None,
        event_type=payload.event_type or payload.milestone or "TELEMATICS_PING",
        description=payload.description or f"Webhook update: {payload.event_type or payload.milestone or 'Location Ping'}",
        occurred_at=payload.occurred_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_name=payload.location_name,
        estimated_delivery_at=payload.estimated_delivery_at,
        idempotency_key=payload.idempotency_key,
        source=TrackingEventSource.WEBHOOK,
        payload=payload.payload or {},
    )

    event = await tracking_service.record_tracking_event(
        session=db,
        shipment_id=shipment_id,
        req=create_req,
        source_override=TrackingEventSource.WEBHOOK,
    )
    return TrackingEventResponse.model_validate(event)


# ============================================================================
# WebSocket Live Tracking Endpoints
# ============================================================================

@router.websocket("/ws/{shipment_id}")
async def shipment_live_tracking_ws(
    websocket: WebSocket,
    shipment_id: uuid.UUID,
    token: Optional[str] = Query(None),
):
    """
    Real-time WebSocket connection for live shipment tracking feeds.
    Authenticates token, verifies authorization for the shipment, and streams live events.
    """
    # 1. Authenticate Token
    if not token:
        # Check Authorization header if query param not provided
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(token)
    if not payload or not payload.get("sub") or not payload.get("org_id"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_org_id = payload.get("org_id")

    # 2. Verify Shipment & Permission
    async with AsyncSessionLocal() as session:
        stmt = select(Shipment).where(Shipment.id == shipment_id)
        shipment = (await session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if str(shipment.organization_id) != user_org_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # 3. Connect to WebSocket Manager
    await tracking_ws_manager.connect_shipment(
        websocket=websocket,
        shipment_id=str(shipment_id),
        org_id=user_org_id,
    )

    try:
        # Send initial confirmation handshake
        await websocket.send_text(json.dumps({
            "type": "SUBSCRIPTION_CONFIRMED",
            "shipment_id": str(shipment_id),
            "tracking_number": shipment.tracking_number,
            "status": shipment.status.value,
            "current_milestone": shipment.current_milestone,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        # Keep connection open and respond to client heartbeats
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": datetime.now(timezone.utc).isoformat()}))
            except Exception:
                pass
    except WebSocketDisconnect:
        await tracking_ws_manager.disconnect_shipment(websocket, str(shipment_id), user_org_id)
    except Exception as e:
        logger.warning(f"WebSocket session terminated with error: {e}")
        await tracking_ws_manager.disconnect_shipment(websocket, str(shipment_id), user_org_id)


@router.websocket("/ws")
async def organization_live_tracking_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Organization-wide WebSocket feed streaming all shipment milestone updates within the tenant.
    """
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(token)
    if not payload or not payload.get("org_id"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_org_id = payload.get("org_id")

    await websocket.accept()
    await tracking_ws_manager.connect_shipment(websocket, "ALL", user_org_id)

    try:
        await websocket.send_text(json.dumps({
            "type": "ORG_STREAM_CONNECTED",
            "org_id": user_org_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": datetime.now(timezone.utc).isoformat()}))
            except Exception:
                pass
    except WebSocketDisconnect:
        await tracking_ws_manager.disconnect_shipment(websocket, "ALL", user_org_id)
    except Exception:
        await tracking_ws_manager.disconnect_shipment(websocket, "ALL", user_org_id)
