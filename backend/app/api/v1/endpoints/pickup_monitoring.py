import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.models.enums import CommitmentStatus, RecoveryStatus
from app.schemas.pickup_monitoring import (
    ArrivalReportRequest,
    PickupCommitmentListResponse,
    PickupCommitmentResponse,
    PickupCompleteRequest,
    PickupFailRequest,
    PickupScanResponse,
    PickupStartRequest,
    RecoveryApproveRequest,
    RecoveryCaseListResponse,
    RecoveryCaseResponse,
    SimulateScenarioRequest,
    SimulateScenarioResponse,
)
from app.services.pickup_monitoring_service import PickupMonitoringService

router = APIRouter(prefix="/pickup-monitoring", tags=["Pickup Monitoring & Accountability"])


@router.get("/commitments", response_model=PickupCommitmentListResponse)
async def list_pickup_commitments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[CommitmentStatus] = Query(None),
    shipment_id: Optional[uuid.UUID] = Query(None),
    transporter_id: Optional[uuid.UUID] = Query(None),
    is_breached: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Lists SLA pickup commitments for the current organization."""
    return await PickupMonitoringService.list_commitments(
        session=session,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        status_filter=status,
        shipment_id=shipment_id,
        transporter_id=transporter_id,
        is_breached=is_breached,
    )


@router.get("/commitments/{commitment_id}", response_model=PickupCommitmentResponse)
async def get_pickup_commitment(
    commitment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Fetches details for a single pickup commitment."""
    return await PickupMonitoringService.get_commitment(
        session=session,
        organization_id=current_user.organization_id,
        commitment_id=commitment_id,
    )


@router.post("/commitments/{commitment_id}/arrival", response_model=PickupCommitmentResponse)
async def report_arrival(
    commitment_id: uuid.UUID,
    payload: ArrivalReportRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Driver or dock manager reports equipment arrival at pickup dock."""
    return await PickupMonitoringService.report_arrival(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        commitment_id=commitment_id,
        data=payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/commitments/{commitment_id}/start", response_model=PickupCommitmentResponse)
async def start_pickup(
    commitment_id: uuid.UUID,
    payload: PickupStartRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Reports cargo loading initiation at dock bay."""
    return await PickupMonitoringService.start_pickup(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        commitment_id=commitment_id,
        data=payload,
    )


@router.post("/commitments/{commitment_id}/complete", response_model=PickupCommitmentResponse)
async def complete_pickup(
    commitment_id: uuid.UUID,
    payload: PickupCompleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Reports pickup completion and vehicle departure."""
    return await PickupMonitoringService.complete_pickup(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        commitment_id=commitment_id,
        data=payload,
    )


@router.post("/commitments/{commitment_id}/fail", response_model=PickupCommitmentResponse)
async def report_pickup_failed(
    commitment_id: uuid.UUID,
    payload: PickupFailRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Explicitly reports pickup failure, breaches commitment, and launches recovery."""
    return await PickupMonitoringService.report_pickup_failed(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        commitment_id=commitment_id,
        data=payload,
    )


@router.post("/scan", response_model=PickupScanResponse)
async def scan_commitments(
    simulated_now: Optional[str] = Query(None, description="Optional simulated clock timestamp for testing"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Triggers scheduled pickup accountability engine scan across all active commitments.
    Protected by distributed Redis lock.
    """
    sim_dt: Optional[datetime] = None
    if simulated_now:
        try:
            clean_str = simulated_now.replace(" ", "+")
            sim_dt = datetime.fromisoformat(clean_str)
            if sim_dt.tzinfo is None:
                sim_dt = sim_dt.replace(tzinfo=timezone.utc)
        except Exception:
            sim_dt = None

    return await PickupMonitoringService.monitor_commitments(
        session=session,
        organization_id=current_user.organization_id,
        simulated_now=sim_dt,
    )


@router.get("/recovery-cases", response_model=RecoveryCaseListResponse)
async def list_recovery_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[RecoveryStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Lists open and resolved recovery cases."""
    return await PickupMonitoringService.list_recovery_cases(
        session=session,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        status_filter=status,
    )


@router.get("/recovery-cases/{case_id}", response_model=RecoveryCaseResponse)
async def get_recovery_case(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Fetches details for a specific recovery case with failure data and replacement recommendations."""
    return await PickupMonitoringService.get_recovery_case(
        session=session,
        organization_id=current_user.organization_id,
        case_id=case_id,
    )


@router.post("/recovery-cases/{case_id}/approve", response_model=RecoveryCaseResponse)
async def approve_recovery_reassignment(
    case_id: uuid.UUID,
    payload: RecoveryApproveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Operations manager approves alternative carrier and creates replacement tender booking."""
    return await PickupMonitoringService.approve_recovery_reassignment(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        recovery_case_id=case_id,
        data=payload,
    )


@router.post("/simulate-scenario", response_model=SimulateScenarioResponse)
async def simulate_reproducible_scenario(
    payload: SimulateScenarioRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Executes the reproducible simulated-time demo:
    - 10 AM shipment scheduled
    - Transporter A accepts
    - Transporter A fails to arrive
    - Failure detected at deadline
    - Transporter C recommended
    - Manager approves
    - Replacement booking created
    - Complete assignment history preserved
    """
    return await PickupMonitoringService.run_simulated_scenario(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=payload,
    )
