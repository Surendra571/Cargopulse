import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, cast, Date, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    BookingStatus,
    CommitmentStatus,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    ShipmentStatus,
)
from app.models.operations import ExceptionRecord, ProofOfDelivery
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.models.transporter import Driver, Transporter, Vehicle
from app.schemas.dashboard import (
    DashboardExceptionItem,
    DashboardMetricsResponse,
    DashboardOverviewResponse,
    DashboardShipmentItem,
    DeliveryPerformanceBreakdown,
    ExceptionDistributionItem,
    PaginatedExceptionsResponse,
    PaginatedShipmentsResponse,
    PickupPerformanceBreakdown,
    RecentActivityItem,
    ShipmentDetailResponse,
    ShipmentEventItem,
    TransporterReliabilityItem,
    VolumeOverTimePoint,
)


class DashboardService:
    @staticmethod
    async def get_overview(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> DashboardOverviewResponse:
        """
        Aggregates complete operational dashboard bundle for the tenant.
        """
        metrics = await DashboardService.get_metrics(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            transporter_id=transporter_id,
        )

        volume_over_time = await DashboardService.get_volume_over_time(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            transporter_id=transporter_id,
        )

        pickup_perf = await DashboardService.get_pickup_performance(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            transporter_id=transporter_id,
        )

        delivery_perf = await DashboardService.get_delivery_performance(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            transporter_id=transporter_id,
        )

        rankings = await DashboardService.get_transporter_rankings(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        exc_types, exc_severities = await DashboardService.get_exceptions_distribution(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            transporter_id=transporter_id,
        )

        recent_activity = await DashboardService.get_recent_activity(
            session=session,
            organization_id=organization_id,
            limit=15,
        )

        return DashboardOverviewResponse(
            metrics=metrics,
            volume_over_time=volume_over_time,
            pickup_performance=pickup_perf,
            delivery_performance=delivery_perf,
            transporter_rankings=rankings,
            exceptions_by_type=exc_types,
            exceptions_by_severity=exc_severities,
            recent_activity=recent_activity,
        )

    @staticmethod
    async def get_metrics(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> DashboardMetricsResponse:
        now = datetime.now(timezone.utc)
        one_hour_ahead = now + timedelta(hours=1)

        # Base filters
        shipment_filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
        ]
        if start_date:
            shipment_filters.append(Shipment.created_at >= start_date)
        if end_date:
            shipment_filters.append(Shipment.created_at <= end_date)
        if transporter_id:
            shipment_filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )

        # 1. Total shipments
        total_q = select(func.count(Shipment.id)).where(and_(*shipment_filters))
        total_shipments = (await session.execute(total_q)).scalar() or 0

        # 2. Pending pickups
        pending_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                Shipment.status.in_([
                    ShipmentStatus.DRAFT,
                    ShipmentStatus.PENDING_ACCEPTANCE,
                    ShipmentStatus.COMMITTED,
                    ShipmentStatus.DISPATCHED,
                ]),
                Shipment.actual_pickup_time.is_(None),
            )
        )
        pending_pickups = (await session.execute(pending_q)).scalar() or 0

        # 3. Confirmed bookings
        booking_filters = [
            TransporterBooking.organization_id == organization_id,
            TransporterBooking.status == BookingStatus.ACCEPTED,
            TransporterBooking.is_deleted.is_(False),
        ]
        if transporter_id:
            booking_filters.append(TransporterBooking.transporter_id == transporter_id)
        if start_date:
            booking_filters.append(TransporterBooking.created_at >= start_date)
        if end_date:
            booking_filters.append(TransporterBooking.created_at <= end_date)

        bookings_q = select(func.count(TransporterBooking.id)).where(and_(*booking_filters))
        confirmed_bookings = (await session.execute(bookings_q)).scalar() or 0

        # 4. Pickups at risk
        at_risk_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                Shipment.actual_pickup_time.is_(None),
                Shipment.status.notin_([ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED]),
                or_(
                    Shipment.scheduled_pickup_time <= one_hour_ahead,
                    Shipment.status == ShipmentStatus.EXCEPTION,
                ),
            )
        )
        pickups_at_risk = (await session.execute(at_risk_q)).scalar() or 0

        # 5. Failed pickups
        failed_pickup_shipment_ids = select(ExceptionRecord.shipment_id).where(
            and_(
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.exception_type.in_([
                    ExceptionType.MISSED_PICKUP,
                    ExceptionType.DELAYED_PICKUP,
                ]),
                ExceptionRecord.is_deleted.is_(False),
            )
        )
        breached_commitments = select(PickupCommitment.shipment_id).where(
            and_(
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_breached.is_(True),
                PickupCommitment.is_deleted.is_(False),
            )
        )

        failed_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                or_(
                    Shipment.id.in_(failed_pickup_shipment_ids),
                    Shipment.id.in_(breached_commitments),
                ),
            )
        )
        failed_pickups = (await session.execute(failed_q)).scalar() or 0

        # 6. In-transit shipments
        in_transit_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                Shipment.status.in_([ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY]),
            )
        )
        in_transit_shipments = (await session.execute(in_transit_q)).scalar() or 0

        # 7. Delayed deliveries
        delayed_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                Shipment.actual_delivery_time.is_(None),
                Shipment.status.notin_([ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED, ShipmentStatus.DRAFT]),
                Shipment.expected_delivery_time < now,
            )
        )
        delayed_deliveries = (await session.execute(delayed_q)).scalar() or 0

        # 8. Delivered shipments
        delivered_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                or_(
                    Shipment.status == ShipmentStatus.DELIVERED,
                    Shipment.actual_delivery_time.is_not(None),
                ),
            )
        )
        delivered_shipments = (await session.execute(delivered_q)).scalar() or 0

        # 9. Open exceptions
        exc_filters = [
            ExceptionRecord.organization_id == organization_id,
            ExceptionRecord.status.in_([
                ExceptionStatus.OPEN,
                ExceptionStatus.INVESTIGATING,
                ExceptionStatus.RECOVERY_IN_PROGRESS,
            ]),
            ExceptionRecord.is_deleted.is_(False),
        ]
        if transporter_id:
            exc_filters.append(
                ExceptionRecord.shipment_id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )
        if start_date:
            exc_filters.append(ExceptionRecord.reported_at >= start_date)
        if end_date:
            exc_filters.append(ExceptionRecord.reported_at <= end_date)

        open_exc_q = select(func.count(ExceptionRecord.id)).where(and_(*exc_filters))
        open_exceptions = (await session.execute(open_exc_q)).scalar() or 0

        # Rates calculation
        # Pickup success rate: Pickups performed without failure
        completed_pickups_q = select(func.count(Shipment.id)).where(
            and_(*shipment_filters, Shipment.actual_pickup_time.is_not(None))
        )
        completed_pickups = (await session.execute(completed_pickups_q)).scalar() or 0
        total_attempted_pickups = completed_pickups + failed_pickups
        if total_attempted_pickups == 0:
            pickup_success_rate = 100.0 if total_shipments > 0 else 0.0
        else:
            pickup_success_rate = round((completed_pickups / total_attempted_pickups) * 100, 1)

        # On-time delivery rate
        on_time_deliv_q = select(func.count(Shipment.id)).where(
            and_(
                *shipment_filters,
                Shipment.actual_delivery_time.is_not(None),
                Shipment.actual_delivery_time <= Shipment.expected_delivery_time,
            )
        )
        on_time_deliveries = (await session.execute(on_time_deliv_q)).scalar() or 0
        if delivered_shipments == 0:
            on_time_delivery_rate = 100.0 if total_shipments > 0 else 0.0
        else:
            on_time_delivery_rate = round((on_time_deliveries / delivered_shipments) * 100, 1)

        return DashboardMetricsResponse(
            total_shipments=total_shipments,
            pending_pickups=pending_pickups,
            confirmed_bookings=confirmed_bookings,
            pickups_at_risk=pickups_at_risk,
            failed_pickups=failed_pickups,
            in_transit_shipments=in_transit_shipments,
            delayed_deliveries=delayed_deliveries,
            delivered_shipments=delivered_shipments,
            open_exceptions=open_exceptions,
            pickup_success_rate=pickup_success_rate,
            on_time_delivery_rate=on_time_delivery_rate,
        )

    @staticmethod
    async def get_volume_over_time(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> List[VolumeOverTimePoint]:
        now = datetime.now(timezone.utc)
        if not start_date:
            start_date = now - timedelta(days=14)
        if not end_date:
            end_date = now

        # Aggregate created shipments per date
        shipment_filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
            Shipment.created_at >= start_date,
            Shipment.created_at <= end_date,
        ]
        if transporter_id:
            shipment_filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )

        date_col = cast(Shipment.created_at, Date)
        q = (
            select(
                date_col.label("day"),
                func.count(Shipment.id).label("total"),
                func.count(
                    case((Shipment.status == ShipmentStatus.DELIVERED, 1), else_=None)
                ).label("delivered"),
            )
            .where(and_(*shipment_filters))
            .group_by(date_col)
            .order_by(date_col)
        )
        rows = (await session.execute(q)).all()
        data_by_day = {str(r.day): (r.total, r.delivered) for r in rows}

        # Query exceptions per day
        exc_filters = [
            ExceptionRecord.organization_id == organization_id,
            ExceptionRecord.is_deleted.is_(False),
            ExceptionRecord.reported_at >= start_date,
            ExceptionRecord.reported_at <= end_date,
        ]
        exc_date_col = cast(ExceptionRecord.reported_at, Date)
        exc_q = (
            select(exc_date_col.label("day"), func.count(ExceptionRecord.id).label("exceptions"))
            .where(and_(*exc_filters))
            .group_by(exc_date_col)
        )
        exc_rows = (await session.execute(exc_q)).all()
        exc_by_day = {str(r.day): r.exceptions for r in exc_rows}

        # Continuous daily series generator
        result: List[VolumeOverTimePoint] = []
        cur = start_date.date()
        stop = end_date.date()
        while cur <= stop:
            d_str = cur.isoformat()
            tot, deliv = data_by_day.get(d_str, (0, 0))
            exc_count = exc_by_day.get(d_str, 0)
            result.append(
                VolumeOverTimePoint(
                    date=d_str,
                    total_shipments=tot,
                    delivered=deliv,
                    exceptions=exc_count,
                )
            )
            cur += timedelta(days=1)

        return result

    @staticmethod
    async def get_pickup_performance(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> PickupPerformanceBreakdown:
        filters = [
            PickupCommitment.organization_id == organization_id,
            PickupCommitment.is_deleted.is_(False),
        ]
        if transporter_id:
            filters.append(PickupCommitment.transporter_id == transporter_id)
        if start_date:
            filters.append(PickupCommitment.created_at >= start_date)
        if end_date:
            filters.append(PickupCommitment.created_at <= end_date)

        total_q = select(func.count(PickupCommitment.id)).where(and_(*filters))
        total = (await session.execute(total_q)).scalar() or 0

        if total == 0:
            return PickupPerformanceBreakdown(
                total_commitments=0, on_time=0, delayed=0, failed=0, success_rate=100.0
            )

        failed_q = select(func.count(PickupCommitment.id)).where(
            and_(*filters, PickupCommitment.is_breached.is_(True))
        )
        failed = (await session.execute(failed_q)).scalar() or 0

        delayed_q = select(func.count(PickupCommitment.id)).where(
            and_(
                *filters,
                PickupCommitment.is_breached.is_(False),
                PickupCommitment.actual_arrival_at.is_not(None),
                PickupCommitment.actual_arrival_at > PickupCommitment.committed_pickup_slot_end,
            )
        )
        delayed = (await session.execute(delayed_q)).scalar() or 0

        on_time_q = select(func.count(PickupCommitment.id)).where(
            and_(
                *filters,
                PickupCommitment.is_breached.is_(False),
                PickupCommitment.actual_arrival_at.is_not(None),
                PickupCommitment.actual_arrival_at <= PickupCommitment.committed_pickup_slot_end,
            )
        )
        on_time = (await session.execute(on_time_q)).scalar() or 0

        success_rate = round(((total - failed) / total) * 100, 1)

        return PickupPerformanceBreakdown(
            total_commitments=total,
            on_time=on_time,
            delayed=delayed,
            failed=failed,
            success_rate=success_rate,
        )

    @staticmethod
    async def get_delivery_performance(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> DeliveryPerformanceBreakdown:
        filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
            Shipment.actual_delivery_time.is_not(None),
        ]
        if transporter_id:
            filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )
        if start_date:
            filters.append(Shipment.actual_delivery_time >= start_date)
        if end_date:
            filters.append(Shipment.actual_delivery_time <= end_date)

        total_q = select(func.count(Shipment.id)).where(and_(*filters))
        total = (await session.execute(total_q)).scalar() or 0

        if total == 0:
            return DeliveryPerformanceBreakdown(
                total_deliveries=0, on_time=0, delayed=0, on_time_rate=100.0
            )

        on_time_q = select(func.count(Shipment.id)).where(
            and_(*filters, Shipment.actual_delivery_time <= Shipment.expected_delivery_time)
        )
        on_time = (await session.execute(on_time_q)).scalar() or 0
        delayed = total - on_time
        on_time_rate = round((on_time / total) * 100, 1)

        return DeliveryPerformanceBreakdown(
            total_deliveries=total,
            on_time=on_time,
            delayed=delayed,
            on_time_rate=on_time_rate,
        )

    @staticmethod
    async def get_transporter_rankings(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[TransporterReliabilityItem]:
        # Fetch transporters active for this organization
        t_stmt = (
            select(Transporter)
            .where(
                and_(
                    Transporter.organization_id == organization_id,
                    Transporter.is_deleted.is_(False),
                )
            )
            .order_by(desc(Transporter.reliability_score))
        )
        transporters = (await session.execute(t_stmt)).scalars().all()

        rankings: List[TransporterReliabilityItem] = []
        for t in transporters:
            # Total shipments assigned / booked with this transporter
            b_stmt = select(func.count(TransporterBooking.id)).where(
                and_(
                    TransporterBooking.organization_id == organization_id,
                    TransporterBooking.transporter_id == t.id,
                    TransporterBooking.is_deleted.is_(False),
                )
            )
            total_loads = (await session.execute(b_stmt)).scalar() or 0

            # On-time pickups
            pk_stmt = select(func.count(PickupCommitment.id)).where(
                and_(
                    PickupCommitment.organization_id == organization_id,
                    PickupCommitment.transporter_id == t.id,
                    PickupCommitment.is_breached.is_(False),
                    PickupCommitment.actual_arrival_at.is_not(None),
                    PickupCommitment.actual_arrival_at <= PickupCommitment.committed_pickup_slot_end,
                )
            )
            on_time_pk = (await session.execute(pk_stmt)).scalar() or 0

            # Active exceptions against this transporter's loads
            exc_stmt = select(func.count(ExceptionRecord.id)).where(
                and_(
                    ExceptionRecord.organization_id == organization_id,
                    ExceptionRecord.status.in_([
                        ExceptionStatus.OPEN,
                        ExceptionStatus.INVESTIGATING,
                        ExceptionStatus.RECOVERY_IN_PROGRESS,
                    ]),
                    ExceptionRecord.shipment_id.in_(
                        select(TransporterBooking.shipment_id).where(
                            TransporterBooking.transporter_id == t.id
                        )
                    ),
                    ExceptionRecord.is_deleted.is_(False),
                )
            )
            active_exc = (await session.execute(exc_stmt)).scalar() or 0

            rankings.append(
                TransporterReliabilityItem(
                    transporter_id=str(t.id),
                    transporter_name=t.name,
                    transporter_code=t.code,
                    total_shipments=total_loads,
                    on_time_pickups=on_time_pk,
                    on_time_deliveries=t.on_time_deliveries,
                    reliability_score=round(t.reliability_score, 1),
                    active_exceptions=active_exc,
                )
            )

        return rankings

    @staticmethod
    async def get_exceptions_distribution(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[ExceptionDistributionItem], List[ExceptionDistributionItem]]:
        filters = [
            ExceptionRecord.organization_id == organization_id,
            ExceptionRecord.is_deleted.is_(False),
        ]
        if transporter_id:
            filters.append(
                ExceptionRecord.shipment_id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )
        if start_date:
            filters.append(ExceptionRecord.reported_at >= start_date)
        if end_date:
            filters.append(ExceptionRecord.reported_at <= end_date)

        total_q = select(func.count(ExceptionRecord.id)).where(and_(*filters))
        total_exceptions = (await session.execute(total_q)).scalar() or 0

        # By Type
        type_q = (
            select(ExceptionRecord.exception_type, func.count(ExceptionRecord.id))
            .where(and_(*filters))
            .group_by(ExceptionRecord.exception_type)
        )
        type_rows = (await session.execute(type_q)).all()

        types_list: List[ExceptionDistributionItem] = []
        for et, cnt in type_rows:
            pct = round((cnt / total_exceptions) * 100, 1) if total_exceptions > 0 else 0.0
            types_list.append(
                ExceptionDistributionItem(
                    category=et.value if hasattr(et, "value") else str(et),
                    count=cnt,
                    percentage=pct,
                )
            )

        # By Severity
        sev_q = (
            select(ExceptionRecord.severity, func.count(ExceptionRecord.id))
            .where(and_(*filters))
            .group_by(ExceptionRecord.severity)
        )
        sev_rows = (await session.execute(sev_q)).all()

        severities_list: List[ExceptionDistributionItem] = []
        for sv, cnt in sev_rows:
            pct = round((cnt / total_exceptions) * 100, 1) if total_exceptions > 0 else 0.0
            severities_list.append(
                ExceptionDistributionItem(
                    category=sv.value if hasattr(sv, "value") else str(sv),
                    count=cnt,
                    percentage=pct,
                )
            )

        return types_list, severities_list

    @staticmethod
    async def get_recent_activity(
        session: AsyncSession,
        organization_id: uuid.UUID,
        limit: int = 15,
    ) -> List[RecentActivityItem]:
        stmt = (
            select(ShipmentEvent, Shipment.tracking_number)
            .join(Shipment, ShipmentEvent.shipment_id == Shipment.id)
            .where(
                and_(
                    ShipmentEvent.organization_id == organization_id,
                    Shipment.is_deleted.is_(False),
                )
            )
            .order_by(desc(ShipmentEvent.occurred_at))
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

        items: List[RecentActivityItem] = []
        for ev, trk in rows:
            items.append(
                RecentActivityItem(
                    id=str(ev.id),
                    shipment_id=str(ev.shipment_id),
                    tracking_number=trk,
                    event_type=ev.event_type,
                    description=ev.description,
                    occurred_at=ev.occurred_at,
                    location_name=ev.location_name,
                    source=ev.source,
                )
            )
        return items

    # ==========================================
    # Operational Tables
    # ==========================================

    @staticmethod
    async def get_attention_shipments(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> PaginatedShipmentsResponse:
        """
        Shipments requiring operational attention:
        - Failed pickups
        - Delayed deliveries
        - In EXCEPTION status or has open critical/high exceptions
        """
        now = datetime.now(timezone.utc)
        shipment_exc_subq = select(ExceptionRecord.shipment_id).where(
            and_(
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.status.in_([
                    ExceptionStatus.OPEN,
                    ExceptionStatus.INVESTIGATING,
                    ExceptionStatus.RECOVERY_IN_PROGRESS,
                ]),
                ExceptionRecord.is_deleted.is_(False),
            )
        )

        filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
            or_(
                Shipment.status == ShipmentStatus.EXCEPTION,
                Shipment.id.in_(shipment_exc_subq),
                and_(
                    Shipment.actual_delivery_time.is_(None),
                    Shipment.status.notin_([ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED, ShipmentStatus.DRAFT]),
                    Shipment.expected_delivery_time < now,
                ),
                and_(
                    Shipment.actual_pickup_time.is_(None),
                    Shipment.status.in_([ShipmentStatus.COMMITTED, ShipmentStatus.DISPATCHED]),
                    Shipment.scheduled_pickup_time < now,
                ),
            ),
        ]

        if search:
            s = f"%{search}%"
            filters.append(
                or_(
                    Shipment.tracking_number.ilike(s),
                    Shipment.origin_city.ilike(s),
                    Shipment.destination_city.ilike(s),
                )
            )

        if transporter_id:
            filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )

        return await DashboardService._paginate_shipments(
            session=session,
            filters=filters,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_upcoming_pickups(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> PaginatedShipmentsResponse:
        """
        Shipments scheduled for pickup in the future or active today without completed pickup.
        """
        filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
            Shipment.actual_pickup_time.is_(None),
            Shipment.status.in_([
                ShipmentStatus.DRAFT,
                ShipmentStatus.PENDING_ACCEPTANCE,
                ShipmentStatus.COMMITTED,
                ShipmentStatus.DISPATCHED,
                ShipmentStatus.AT_PICKUP,
            ]),
        ]

        if search:
            s = f"%{search}%"
            filters.append(
                or_(
                    Shipment.tracking_number.ilike(s),
                    Shipment.origin_city.ilike(s),
                    Shipment.destination_city.ilike(s),
                )
            )

        if transporter_id:
            filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )

        return await DashboardService._paginate_shipments(
            session=session,
            filters=filters,
            order_by_col=Shipment.scheduled_pickup_time.asc(),
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_failed_pickups(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> PaginatedShipmentsResponse:
        """
        Shipments where pickup failed, breached commitment, or missed slot.
        """
        breached_commitments = select(PickupCommitment.shipment_id).where(
            and_(
                PickupCommitment.organization_id == organization_id,
                PickupCommitment.is_breached.is_(True),
                PickupCommitment.is_deleted.is_(False),
            )
        )
        pickup_exc = select(ExceptionRecord.shipment_id).where(
            and_(
                ExceptionRecord.organization_id == organization_id,
                ExceptionRecord.exception_type.in_([
                    ExceptionType.MISSED_PICKUP,
                    ExceptionType.DELAYED_PICKUP,
                ]),
                ExceptionRecord.is_deleted.is_(False),
            )
        )

        filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
            or_(
                Shipment.id.in_(breached_commitments),
                Shipment.id.in_(pickup_exc),
            ),
        ]

        if search:
            s = f"%{search}%"
            filters.append(
                or_(
                    Shipment.tracking_number.ilike(s),
                    Shipment.origin_city.ilike(s),
                    Shipment.destination_city.ilike(s),
                )
            )

        if transporter_id:
            filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )

        return await DashboardService._paginate_shipments(
            session=session,
            filters=filters,
            order_by_col=Shipment.scheduled_pickup_time.desc(),
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_recent_deliveries(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> PaginatedShipmentsResponse:
        """
        Completed delivered shipments.
        """
        filters = [
            Shipment.organization_id == organization_id,
            Shipment.is_deleted.is_(False),
            or_(
                Shipment.status == ShipmentStatus.DELIVERED,
                Shipment.actual_delivery_time.is_not(None),
            ),
        ]

        if search:
            s = f"%{search}%"
            filters.append(
                or_(
                    Shipment.tracking_number.ilike(s),
                    Shipment.origin_city.ilike(s),
                    Shipment.destination_city.ilike(s),
                )
            )

        if transporter_id:
            filters.append(
                Shipment.id.in_(
                    select(TransporterBooking.shipment_id).where(
                        and_(
                            TransporterBooking.transporter_id == transporter_id,
                            TransporterBooking.is_deleted.is_(False),
                        )
                    )
                )
            )

        return await DashboardService._paginate_shipments(
            session=session,
            filters=filters,
            order_by_col=Shipment.actual_delivery_time.desc(),
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_open_exceptions(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        severity: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedExceptionsResponse:
        filters = [
            ExceptionRecord.organization_id == organization_id,
            ExceptionRecord.status.in_([
                ExceptionStatus.OPEN,
                ExceptionStatus.INVESTIGATING,
                ExceptionStatus.RECOVERY_IN_PROGRESS,
            ]),
            ExceptionRecord.is_deleted.is_(False),
        ]
        if severity:
            filters.append(ExceptionRecord.severity == severity)
        if search:
            s = f"%{search}%"
            filters.append(
                or_(
                    ExceptionRecord.title.ilike(s),
                    ExceptionRecord.description.ilike(s),
                )
            )

        count_q = select(func.count(ExceptionRecord.id)).where(and_(*filters))
        total = (await session.execute(count_q)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        stmt = (
            select(ExceptionRecord, Shipment.tracking_number)
            .join(Shipment, ExceptionRecord.shipment_id == Shipment.id)
            .where(and_(*filters))
            .order_by(desc(ExceptionRecord.reported_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).all()

        items: List[DashboardExceptionItem] = []
        for exc, trk in rows:
            items.append(
                DashboardExceptionItem(
                    id=str(exc.id),
                    shipment_id=str(exc.shipment_id),
                    tracking_number=trk,
                    exception_type=exc.exception_type.value if hasattr(exc.exception_type, "value") else str(exc.exception_type),
                    severity=exc.severity.value if hasattr(exc.severity, "value") else str(exc.severity),
                    status=exc.status.value if hasattr(exc.status, "value") else str(exc.status),
                    title=exc.title,
                    description=exc.description,
                    reported_at=exc.reported_at,
                )
            )

        return PaginatedExceptionsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def get_shipment_detail(
        session: AsyncSession,
        organization_id: uuid.UUID,
        shipment_id: uuid.UUID,
    ) -> Optional[ShipmentDetailResponse]:
        """
        Detailed operational view of a single shipment.
        """
        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.vehicle),
                selectinload(Shipment.assignments).selectinload(ShipmentAssignment.driver),
                selectinload(Shipment.events),
                selectinload(Shipment.exceptions),
                selectinload(Shipment.proof_of_delivery),
            )
            .where(
                and_(
                    Shipment.id == shipment_id,
                    Shipment.organization_id == organization_id,
                    Shipment.is_deleted.is_(False),
                )
            )
        )
        shipment = (await session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            return None

        # Resolve primary transporter
        transporter_name = None
        transporter_id = None
        for b in shipment.bookings:
            if b.status == BookingStatus.ACCEPTED and b.transporter:
                transporter_name = b.transporter.name
                transporter_id = str(b.transporter_id)
                break
        if not transporter_name and shipment.bookings:
            b = shipment.bookings[0]
            if b.transporter:
                transporter_name = b.transporter.name
                transporter_id = str(b.transporter_id)

        # Resolve driver / vehicle
        driver_name = None
        vehicle_plate = None
        for a in shipment.assignments:
            if a.driver:
                driver_name = a.driver.full_name
            if a.vehicle:
                vehicle_plate = a.vehicle.license_plate
            break

        # Map events
        event_items = [
            ShipmentEventItem(
                id=str(ev.id),
                event_type=ev.event_type,
                description=ev.description,
                occurred_at=ev.occurred_at,
                location_name=ev.location_name,
                source=ev.source,
                latitude=ev.latitude,
                longitude=ev.longitude,
            )
            for ev in sorted(shipment.events, key=lambda x: x.occurred_at)
        ]

        # Map exceptions
        exc_items = [
            DashboardExceptionItem(
                id=str(ex.id),
                shipment_id=str(shipment.id),
                tracking_number=shipment.tracking_number,
                exception_type=ex.exception_type.value if hasattr(ex.exception_type, "value") else str(ex.exception_type),
                severity=ex.severity.value if hasattr(ex.severity, "value") else str(ex.severity),
                status=ex.status.value if hasattr(ex.status, "value") else str(ex.status),
                title=ex.title,
                description=ex.description,
                reported_at=ex.reported_at,
                transporter_name=transporter_name,
            )
            for ex in shipment.exceptions
        ]

        # POD details
        pod_verified = False
        pod_signatory = None
        pod_verified_at = None
        if shipment.proof_of_delivery:
            pod = shipment.proof_of_delivery
            pod_verified = pod.verification_status.value == "VERIFIED" if hasattr(pod.verification_status, "value") else pod.verification_status == "VERIFIED"
            pod_signatory = pod.signed_by_name
            pod_verified_at = pod.verified_at or pod.created_at

        return ShipmentDetailResponse(
            id=str(shipment.id),
            tracking_number=shipment.tracking_number,
            status=shipment.status.value if hasattr(shipment.status, "value") else str(shipment.status),
            origin_name=shipment.origin_name,
            origin_address=shipment.origin_address,
            origin_city=shipment.origin_city,
            origin_state=shipment.origin_state,
            origin_contact_name=shipment.origin_contact_name,
            origin_contact_phone=shipment.origin_contact_phone,
            destination_name=shipment.destination_name,
            destination_address=shipment.destination_address,
            destination_city=shipment.destination_city,
            destination_state=shipment.destination_state,
            destination_contact_name=shipment.destination_contact_name,
            destination_contact_phone=shipment.destination_contact_phone,
            scheduled_pickup_time=shipment.scheduled_pickup_time,
            actual_pickup_time=shipment.actual_pickup_time,
            expected_delivery_time=shipment.expected_delivery_time,
            actual_delivery_time=shipment.actual_delivery_time,
            total_weight_kg=float(shipment.total_weight_kg),
            package_count=shipment.package_count,
            goods_description=shipment.goods_description,
            is_hazardous=shipment.is_hazardous,
            transporter_id=transporter_id,
            transporter_name=transporter_name,
            driver_name=driver_name,
            vehicle_plate=vehicle_plate,
            events=event_items,
            exceptions=exc_items,
            pod_verified=pod_verified,
            pod_signatory_name=pod_signatory,
            pod_verified_at=pod_verified_at,
            created_at=shipment.created_at,
        )

    # ==========================================
    # Helper Paginate
    # ==========================================

    @staticmethod
    async def _paginate_shipments(
        session: AsyncSession,
        filters: List[Any],
        order_by_col: Any = desc(Shipment.created_at),
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedShipmentsResponse:
        count_q = select(func.count(Shipment.id)).where(and_(*filters))
        total = (await session.execute(count_q)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        now = datetime.now(timezone.utc)
        one_hour_ahead = now + timedelta(hours=1)

        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.bookings).selectinload(TransporterBooking.transporter),
                selectinload(Shipment.exceptions),
            )
            .where(and_(*filters))
            .order_by(order_by_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        shipments = (await session.execute(stmt)).scalars().all()

        items: List[DashboardShipmentItem] = []
        for s in shipments:
            # Transporter
            t_name = None
            t_id = None
            for b in s.bookings:
                if b.status == BookingStatus.ACCEPTED and b.transporter:
                    t_name = b.transporter.name
                    t_id = str(b.transporter_id)
                    break
            if not t_name and s.bookings:
                b = s.bookings[0]
                if b.transporter:
                    t_name = b.transporter.name
                    t_id = str(b.transporter_id)

            open_exc_cnt = sum(
                1 for e in s.exceptions
                if e.status in [ExceptionStatus.OPEN, ExceptionStatus.INVESTIGATING, ExceptionStatus.RECOVERY_IN_PROGRESS]
            )

            is_at_risk = (
                s.actual_pickup_time is None
                and s.status not in [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED]
                and (s.scheduled_pickup_time <= one_hour_ahead or s.status == ShipmentStatus.EXCEPTION or open_exc_cnt > 0)
            )

            items.append(
                DashboardShipmentItem(
                    id=str(s.id),
                    tracking_number=s.tracking_number,
                    status=s.status.value if hasattr(s.status, "value") else str(s.status),
                    origin_city=s.origin_city,
                    origin_state=s.origin_state,
                    destination_city=s.destination_city,
                    destination_state=s.destination_state,
                    transporter_id=t_id,
                    transporter_name=t_name,
                    scheduled_pickup_time=s.scheduled_pickup_time,
                    expected_delivery_time=s.expected_delivery_time,
                    actual_pickup_time=s.actual_pickup_time,
                    actual_delivery_time=s.actual_delivery_time,
                    total_weight_kg=float(s.total_weight_kg),
                    package_count=s.package_count,
                    is_at_risk=is_at_risk,
                    open_exceptions_count=open_exc_cnt,
                    created_at=s.created_at,
                )
            )

        return PaginatedShipmentsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
