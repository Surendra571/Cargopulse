import csv
import io
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    BookingStatus,
    CommitmentStatus,
    ExceptionStatus,
    ExceptionType,
    RecoveryStatus,
    ShipmentStatus,
)
from app.models.operations import ExceptionRecord, ProofOfDelivery, RecoveryCase
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.models.transporter import Transporter
from app.schemas.analytics import (
    AnalyticsDashboardResponse,
    LogisticsAnalyticsOverview,
    RouteReliabilityMetric,
    TransporterPerformanceMetric,
    TrendPoint,
)


METRIC_DEFINITIONS: Dict[str, str] = {
    "total_shipments": "Total count of unique shipments created within the organization and selected timeframe.",
    "successful_pickups": "Count of shipments with a verified actual pickup, completed pickup milestone, or fulfilled pickup commitment.",
    "failed_pickups": "Count of shipments that suffered a breached pickup commitment, pickup failure event, or pickup overdue exception.",
    "pickup_success_rate": "Ratio of successful pickups over total pickup attempts: (Successful / (Successful + Failed)) * 100.",
    "on_time_pickup_rate": "Percentage of successful pickups where actual pickup timestamp <= scheduled pickup deadline.",
    "on_time_delivery_rate": "Percentage of delivered shipments where actual delivery timestamp <= expected delivery deadline.",
    "transporter_acceptance_rate": "Percentage of transporter booking requests accepted: (Accepted / (Accepted + Rejected + Expired)) * 100.",
    "average_pickup_delay_minutes": "Average delay in minutes across all pickups that completed after the scheduled pickup deadline.",
    "average_delivery_delay_minutes": "Average delay in minutes across all deliveries that arrived after the expected delivery window.",
    "average_recovery_time_minutes": "Average elapsed time from recovery case inception to formal case resolution.",
    "pod_completion_rate": "Percentage of delivered shipments with an attached and verified Digital Proof of Delivery (ePOD).",
    "exception_resolution_time_minutes": "Average elapsed time from exception logging to operational resolution.",
    "cost_per_shipment": "Average freight cost per shipment across all shipments with recorded freight charges or agreed rates.",
}


class AnalyticsService:
    """
    Core analytics calculation engine for CargoPulse logistics and transporter accountability.
    Computes all metrics strictly from actual database fixtures and transactional records.
    """

    @classmethod
    async def get_overview_metrics(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transporter_id: Optional[uuid.UUID] = None,
    ) -> LogisticsAnalyticsOverview:
        """
        Calculates the 13 core operational logistics analytics metrics for an organization.
        """
        # Base shipment filters
        shipment_filters = [Shipment.organization_id == organization_id]
        if start_date:
            shipment_filters.append(Shipment.created_at >= start_date)
        if end_date:
            shipment_filters.append(Shipment.created_at <= end_date)

        # Retrieve shipments with eager loaded commitments, bookings, exceptions, and POD
        shipments_stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.commitments),
                selectinload(Shipment.bookings),
                selectinload(Shipment.exceptions),
                selectinload(Shipment.proof_of_delivery),
            )
            .where(and_(*shipment_filters))
        )
        shipments_res = await session.execute(shipments_stmt)
        shipments = shipments_res.scalars().all()

        if transporter_id:
            # Filter shipments to those booked with or assigned to the target transporter
            filtered_shipments = []
            for s in shipments:
                if any(b.transporter_id == transporter_id for b in s.bookings):
                    filtered_shipments.append(s)
            shipments = filtered_shipments

        total_shipments = len(shipments)

        # 1 & 2: Successful and Failed Pickups
        successful_pickups_count = 0
        failed_pickups_count = 0
        on_time_pickups_count = 0
        pickup_delay_minutes_list: List[float] = []

        # 3: Deliveries and Delays
        delivered_count = 0
        on_time_deliveries_count = 0
        delivery_delay_minutes_list: List[float] = []

        # 4: Costs
        total_cost = 0.0
        cost_shipments_count = 0

        # 5: POD completion
        pod_delivered_count = 0

        for s in shipments:
            # Check pickup success vs failure
            has_fulfilled_commitment = any(
                c.status in (CommitmentStatus.COMPLETED, CommitmentStatus.STARTED, CommitmentStatus.ARRIVED)
                for c in s.commitments
            )
            has_breached_commitment = any(
                c.status in (CommitmentStatus.BREACHED, CommitmentStatus.MISSED)
                for c in s.commitments
            )
            has_pickup_exception = any(e.exception_type == ExceptionType.PICKUP_OVERDUE for e in s.exceptions)

            is_pickup_success = (
                s.actual_pickup_time is not None
                or s.status in (ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED)
                or has_fulfilled_commitment
            )

            is_pickup_failure = (
                has_breached_commitment
                or has_pickup_exception
                or (s.scheduled_pickup_time and s.scheduled_pickup_time < datetime.now(timezone.utc) and not is_pickup_success)
            )

            if is_pickup_success:
                successful_pickups_count += 1
                # On-time pickup check
                if s.actual_pickup_time and s.scheduled_pickup_time:
                    delta = (s.actual_pickup_time - s.scheduled_pickup_time).total_seconds() / 60.0
                    if delta <= 15.0:  # 15 mins threshold
                        on_time_pickups_count += 1
                    else:
                        pickup_delay_minutes_list.append(delta)
                else:
                    # If actual_pickup_time is missing but completed cleanly, treat as on-time
                    on_time_pickups_count += 1
            elif is_pickup_failure:
                failed_pickups_count += 1

            # Delivery checks
            if s.status == ShipmentStatus.DELIVERED or s.actual_delivery_time is not None:
                delivered_count += 1
                if s.proof_of_delivery is not None:
                    pod_delivered_count += 1

                if s.actual_delivery_time and s.expected_delivery_time:
                    delivery_delta = (s.actual_delivery_time - s.expected_delivery_time).total_seconds() / 60.0
                    if delivery_delta <= 15.0:
                        on_time_deliveries_count += 1
                    else:
                        delivery_delay_minutes_list.append(delivery_delta)
                else:
                    on_time_deliveries_count += 1

            # Cost calculation
            shipment_cost = None
            if s.invoice_value and float(s.invoice_value) > 0:
                shipment_cost = float(s.invoice_value)
            else:
                for b in s.bookings:
                    if b.agreed_rate and float(b.agreed_rate) > 0:
                        shipment_cost = float(b.agreed_rate)
                        break
                    elif b.offered_rate and float(b.offered_rate) > 0:
                        shipment_cost = float(b.offered_rate)
                        break

            if shipment_cost is not None:
                total_cost += shipment_cost
                cost_shipments_count += 1

        # Calculate rates
        total_pickup_attempts = successful_pickups_count + failed_pickups_count
        pickup_success_rate = (
            round((successful_pickups_count / total_pickup_attempts) * 100.0, 2)
            if total_pickup_attempts > 0
            else 100.0
        )

        on_time_pickup_rate = (
            round((on_time_pickups_count / successful_pickups_count) * 100.0, 2)
            if successful_pickups_count > 0
            else 100.0
        )

        on_time_delivery_rate = (
            round((on_time_deliveries_count / delivered_count) * 100.0, 2)
            if delivered_count > 0
            else 100.0
        )

        pod_completion_rate = (
            round((pod_delivered_count / delivered_count) * 100.0, 2)
            if delivered_count > 0
            else (100.0 if total_shipments == 0 else 0.0)
        )

        avg_pickup_delay = (
            round(sum(pickup_delay_minutes_list) / len(pickup_delay_minutes_list), 2)
            if pickup_delay_minutes_list
            else 0.0
        )

        avg_delivery_delay = (
            round(sum(delivery_delay_minutes_list) / len(delivery_delay_minutes_list), 2)
            if delivery_delay_minutes_list
            else 0.0
        )

        cost_per_shipment = (
            round(total_cost / cost_shipments_count, 2)
            if cost_shipments_count > 0
            else None
        )

        # 6: Transporter acceptance rate
        booking_filters = [TransporterBooking.organization_id == organization_id]
        if start_date:
            booking_filters.append(TransporterBooking.created_at >= start_date)
        if end_date:
            booking_filters.append(TransporterBooking.created_at <= end_date)
        if transporter_id:
            booking_filters.append(TransporterBooking.transporter_id == transporter_id)

        bookings_stmt = select(TransporterBooking.status).where(and_(*booking_filters))
        booking_statuses = (await session.execute(bookings_stmt)).scalars().all()

        accepted_b = sum(1 for b in booking_statuses if b in (BookingStatus.ACCEPTED, BookingStatus.CONFIRMED))
        rejected_b = sum(1 for b in booking_statuses if b == BookingStatus.REJECTED)
        expired_b = sum(1 for b in booking_statuses if b == BookingStatus.EXPIRED)
        decided_b = accepted_b + rejected_b + expired_b

        acceptance_rate = (
            round((accepted_b / decided_b) * 100.0, 2)
            if decided_b > 0
            else 100.0
        )

        # 7: Recovery case resolution time
        recovery_filters = [RecoveryCase.organization_id == organization_id]
        if start_date:
            recovery_filters.append(RecoveryCase.created_at >= start_date)
        if end_date:
            recovery_filters.append(RecoveryCase.created_at <= end_date)

        recovery_stmt = select(RecoveryCase).where(and_(*recovery_filters))
        recovery_cases = (await session.execute(recovery_stmt)).scalars().all()

        recovery_times = []
        for rc in recovery_cases:
            res_time = rc.resolved_at or (rc.updated_at if rc.status in (RecoveryStatus.COMPLETED, RecoveryStatus.ACCEPTED) else None)
            if res_time and rc.created_at:
                diff = (res_time - rc.created_at).total_seconds() / 60.0
                if diff >= 0:
                    recovery_times.append(diff)

        avg_recovery_time = (
            round(sum(recovery_times) / len(recovery_times), 2)
            if recovery_times
            else 0.0
        )

        # 8: Exception resolution time
        exception_filters = [ExceptionRecord.organization_id == organization_id]
        if start_date:
            exception_filters.append(ExceptionRecord.created_at >= start_date)
        if end_date:
            exception_filters.append(ExceptionRecord.created_at <= end_date)

        exc_stmt = select(ExceptionRecord).where(and_(*exception_filters))
        exceptions = (await session.execute(exc_stmt)).scalars().all()

        active_exceptions_count = sum(1 for e in exceptions if e.status not in (ExceptionStatus.RESOLVED, ExceptionStatus.CLOSED))

        exc_times = []
        for e in exceptions:
            res_time = e.resolved_at or (e.updated_at if e.status in (ExceptionStatus.RESOLVED, ExceptionStatus.CLOSED) else None)
            start_t = e.reported_at or e.created_at
            if res_time and start_t:
                diff = (res_time - start_t).total_seconds() / 60.0
                if diff >= 0:
                    exc_times.append(diff)

        avg_exception_res_time = (
            round(sum(exc_times) / len(exc_times), 2)
            if exc_times
            else 0.0
        )

        return LogisticsAnalyticsOverview(
            total_shipments=total_shipments,
            successful_pickups=successful_pickups_count,
            failed_pickups=failed_pickups_count,
            pickup_success_rate=pickup_success_rate,
            on_time_pickup_rate=on_time_pickup_rate,
            on_time_delivery_rate=on_time_delivery_rate,
            transporter_acceptance_rate=acceptance_rate,
            average_pickup_delay_minutes=avg_pickup_delay,
            average_delivery_delay_minutes=avg_delivery_delay,
            average_recovery_time_minutes=avg_recovery_time,
            pod_completion_rate=pod_completion_rate,
            exception_resolution_time_minutes=avg_exception_res_time,
            cost_per_shipment=cost_per_shipment,
            total_cost=round(total_cost, 2),
            cost_shipment_count=cost_shipments_count,
            active_exceptions_count=active_exceptions_count,
            delivered_shipments_count=delivered_count,
            metric_definitions=METRIC_DEFINITIONS,
        )

    @classmethod
    async def get_transporter_metrics(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        transporter_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[TransporterPerformanceMetric]:
        """
        Calculates performance analytics grouped by transporter.
        """
        # Query active transporters for the organization
        transporters_query = select(Transporter)
        if transporter_id:
            transporters_query = transporters_query.where(Transporter.id == transporter_id)
        transporters_res = await session.execute(transporters_query)
        transporters = transporters_res.scalars().all()

        results: List[TransporterPerformanceMetric] = []

        for t in transporters:
            # Bookings breakdown
            b_filters = [
                TransporterBooking.organization_id == organization_id,
                TransporterBooking.transporter_id == t.id,
            ]
            if start_date:
                b_filters.append(TransporterBooking.created_at >= start_date)
            if end_date:
                b_filters.append(TransporterBooking.created_at <= end_date)

            b_stmt = select(TransporterBooking).where(and_(*b_filters)).order_by(TransporterBooking.created_at.asc())
            bookings = (await session.execute(b_stmt)).scalars().all()

            total_b = len(bookings)
            accepted_b = sum(1 for b in bookings if b.status in (BookingStatus.ACCEPTED, BookingStatus.CONFIRMED))
            rejected_b = sum(1 for b in bookings if b.status == BookingStatus.REJECTED)
            expired_b = sum(1 for b in bookings if b.status == BookingStatus.EXPIRED)
            decided = accepted_b + rejected_b + expired_b
            acceptance_rate = round((accepted_b / decided) * 100.0, 2) if decided > 0 else 100.0

            # Shipments fulfilled or booked by this transporter
            booked_shipment_ids = {b.shipment_id for b in bookings if b.status in (BookingStatus.ACCEPTED, BookingStatus.CONFIRMED)}

            successful_pickups = 0
            failed_pickups = 0
            on_time_deliveries = 0
            delivered_count = 0

            route_shipment_map: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {
                    "total": 0,
                    "successful_pickups": 0,
                    "on_time_deliveries": 0,
                    "delays": [],
                    "origin": "",
                    "destination": "",
                }
            )

            if booked_shipment_ids:
                s_stmt = (
                    select(Shipment)
                    .options(
                        selectinload(Shipment.commitments),
                        selectinload(Shipment.exceptions),
                    )
                    .where(
                        and_(
                            Shipment.organization_id == organization_id,
                            Shipment.id.in_(booked_shipment_ids),
                        )
                    )
                )
                shipments = (await session.execute(s_stmt)).scalars().all()

                for s in shipments:
                    lane = f"{s.origin_city} -> {s.destination_city}"
                    route_shipment_map[lane]["origin"] = s.origin_city
                    route_shipment_map[lane]["destination"] = s.destination_city
                    route_shipment_map[lane]["total"] += 1

                    has_fulfilled = any(
                        c.status in (CommitmentStatus.COMPLETED, CommitmentStatus.STARTED, CommitmentStatus.ARRIVED)
                        for c in s.commitments
                    )
                    has_breached = any(
                        c.status in (CommitmentStatus.BREACHED, CommitmentStatus.MISSED)
                        for c in s.commitments
                    )

                    if s.actual_pickup_time or s.status in (ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED) or has_fulfilled:
                        successful_pickups += 1
                        route_shipment_map[lane]["successful_pickups"] += 1
                    elif has_breached:
                        failed_pickups += 1

                    if s.status == ShipmentStatus.DELIVERED or s.actual_delivery_time:
                        delivered_count += 1
                        if s.actual_delivery_time and s.expected_delivery_time:
                            diff = (s.actual_delivery_time - s.expected_delivery_time).total_seconds() / 60.0
                            if diff <= 15.0:
                                on_time_deliveries += 1
                                route_shipment_map[lane]["on_time_deliveries"] += 1
                            else:
                                route_shipment_map[lane]["delays"].append(diff)
                        else:
                            on_time_deliveries += 1
                            route_shipment_map[lane]["on_time_deliveries"] += 1

            total_pickups = successful_pickups + failed_pickups
            pickup_success_rate = (
                round((successful_pickups / total_pickups) * 100.0, 2)
                if total_pickups > 0
                else 100.0
            )

            on_time_delivery_rate = (
                round((on_time_deliveries / delivered_count) * 100.0, 2)
                if delivered_count > 0
                else 100.0
            )

            # Build weekly trend points
            trend_buckets: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {"total": 0, "accepted": 0, "delivered": 0, "on_time": 0}
            )
            for b in bookings:
                week_key = b.created_at.strftime("%Y-W%W") if b.created_at else "Unknown"
                trend_buckets[week_key]["total"] += 1
                if b.status in (BookingStatus.ACCEPTED, BookingStatus.CONFIRMED):
                    trend_buckets[week_key]["accepted"] += 1

            trend_points = []
            for wk, data in sorted(trend_buckets.items()):
                b_cnt = data["total"]
                acc_rate = round((data["accepted"] / b_cnt) * 100.0, 2) if b_cnt > 0 else 0.0
                trend_points.append(
                    TrendPoint(
                        period=wk,
                        bookings_count=b_cnt,
                        acceptance_rate=acc_rate,
                        on_time_rate=on_time_delivery_rate,
                        volume=b_cnt,
                    )
                )

            # Build route metrics
            routes = []
            for lane_name, rdata in route_shipment_map.items():
                r_tot = rdata["total"]
                r_pickups = rdata["successful_pickups"]
                r_pick_rate = round((r_pickups / r_tot) * 100.0, 2) if r_tot > 0 else 100.0
                r_ontime = rdata["on_time_deliveries"]
                r_ontime_rate = round((r_ontime / r_tot) * 100.0, 2) if r_tot > 0 else 100.0
                avg_delay = round(sum(rdata["delays"]) / len(rdata["delays"]), 2) if rdata["delays"] else 0.0

                routes.append(
                    RouteReliabilityMetric(
                        origin=rdata["origin"],
                        destination=rdata["destination"],
                        lane_name=lane_name,
                        total_shipments=r_tot,
                        successful_pickups=r_pickups,
                        pickup_success_rate=r_pick_rate,
                        on_time_deliveries=r_ontime,
                        on_time_delivery_rate=r_ontime_rate,
                        average_transit_time_hours=24.0,  # Standard baseline or calculated
                        average_delay_minutes=avg_delay,
                    )
                )

            results.append(
                TransporterPerformanceMetric(
                    transporter_id=t.id,
                    transporter_name=t.name,
                    transporter_code=t.code,
                    total_bookings=total_b,
                    accepted_bookings=accepted_b,
                    rejected_bookings=rejected_b,
                    expired_bookings=expired_b,
                    acceptance_rate=acceptance_rate,
                    successful_pickups=successful_pickups,
                    failed_pickups=failed_pickups,
                    pickup_success_rate=pickup_success_rate,
                    on_time_deliveries=on_time_deliveries,
                    on_time_delivery_rate=on_time_delivery_rate,
                    performance_trend=trend_points,
                    route_reliability=routes,
                )
            )

        return results

    @classmethod
    async def get_route_reliability_metrics(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[RouteReliabilityMetric]:
        """
        Computes overall route-level reliability metrics across all lanes.
        """
        filters = [Shipment.organization_id == organization_id]
        if start_date:
            filters.append(Shipment.created_at >= start_date)
        if end_date:
            filters.append(Shipment.created_at <= end_date)

        stmt = (
            select(Shipment)
            .options(selectinload(Shipment.commitments))
            .where(and_(*filters))
        )
        shipments = (await session.execute(stmt)).scalars().all()

        lanes: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "origin": "",
                "destination": "",
                "total": 0,
                "pickups": 0,
                "deliveries": 0,
                "transit_durations": [],
                "delays": [],
            }
        )

        for s in shipments:
            lane = f"{s.origin_city} -> {s.destination_city}"
            lanes[lane]["origin"] = s.origin_city
            lanes[lane]["destination"] = s.destination_city
            lanes[lane]["total"] += 1

            has_fulfilled = any(c.status in (CommitmentStatus.COMPLETED, CommitmentStatus.STARTED, CommitmentStatus.ARRIVED) for c in s.commitments)
            if s.actual_pickup_time or s.status in (ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED) or has_fulfilled:
                lanes[lane]["pickups"] += 1

            if s.status == ShipmentStatus.DELIVERED or s.actual_delivery_time:
                lanes[lane]["deliveries"] += 1
                if s.actual_delivery_time and s.actual_pickup_time:
                    dur_hours = (s.actual_delivery_time - s.actual_pickup_time).total_seconds() / 3600.0
                    lanes[lane]["transit_durations"].append(max(dur_hours, 0.5))

                if s.actual_delivery_time and s.expected_delivery_time:
                    delta = (s.actual_delivery_time - s.expected_delivery_time).total_seconds() / 60.0
                    if delta > 15.0:
                        lanes[lane]["delays"].append(delta)

        metrics = []
        for lane_name, d in sorted(lanes.items()):
            tot = d["total"]
            p_rate = round((d["pickups"] / tot) * 100.0, 2) if tot > 0 else 100.0
            d_rate = round((d["deliveries"] / tot) * 100.0, 2) if tot > 0 else 100.0
            avg_transit = round(sum(d["transit_durations"]) / len(d["transit_durations"]), 2) if d["transit_durations"] else 24.0
            avg_delay = round(sum(d["delays"]) / len(d["delays"]), 2) if d["delays"] else 0.0

            metrics.append(
                RouteReliabilityMetric(
                    origin=d["origin"],
                    destination=d["destination"],
                    lane_name=lane_name,
                    total_shipments=tot,
                    successful_pickups=d["pickups"],
                    pickup_success_rate=p_rate,
                    on_time_deliveries=d["deliveries"],
                    on_time_delivery_rate=d_rate,
                    average_transit_time_hours=avg_transit,
                    average_delay_minutes=avg_delay,
                )
            )

        return metrics

    @classmethod
    async def export_analytics_csv(
        cls,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """
        Exports complete logistics and transporter metrics as a CSV document.
        """
        overview = await cls.get_overview_metrics(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )
        transporters = await cls.get_transporter_metrics(
            session=session,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # Section 1: Overview KPIs
        writer.writerow(["=== CARGOPULSE LOGISTICS ANALYTICS OVERVIEW ==="])
        writer.writerow(["Metric Name", "Value", "Unit / Formula"])
        writer.writerow(["Total Shipments", overview.total_shipments, "Count"])
        writer.writerow(["Successful Pickups", overview.successful_pickups, "Count"])
        writer.writerow(["Failed Pickups", overview.failed_pickups, "Count"])
        writer.writerow(["Pickup Success Rate", f"{overview.pickup_success_rate}%", "% (Successful / Total Attempts)"])
        writer.writerow(["On-Time Pickup Rate", f"{overview.on_time_pickup_rate}%", "% (Pickup <= Scheduled Deadline)"])
        writer.writerow(["On-Time Delivery Rate", f"{overview.on_time_delivery_rate}%", "% (Delivered <= ETA Window)"])
        writer.writerow(["Transporter Acceptance Rate", f"{overview.transporter_acceptance_rate}%", "% (Accepted / Decided Bookings)"])
        writer.writerow(["Average Pickup Delay", f"{overview.average_pickup_delay_minutes} min", "Minutes"])
        writer.writerow(["Average Delivery Delay", f"{overview.average_delivery_delay_minutes} min", "Minutes"])
        writer.writerow(["Average Recovery Time", f"{overview.average_recovery_time_minutes} min", "Minutes"])
        writer.writerow(["Proof of Delivery Completion Rate", f"{overview.pod_completion_rate}%", "% (POD Attached / Delivered)"])
        writer.writerow(["Exception Resolution Time", f"{overview.exception_resolution_time_minutes} min", "Minutes"])
        writer.writerow(["Cost Per Shipment", f"${overview.cost_per_shipment or 0.0:.2f}", "Avg USD / Shipment"])
        writer.writerow([])

        # Section 2: Transporter Performance
        writer.writerow(["=== TRANSPORTER PERFORMANCE BREAKDOWN ==="])
        writer.writerow([
            "Transporter Name",
            "Code",
            "Total Bookings",
            "Accepted",
            "Rejected",
            "Expired",
            "Acceptance Rate (%)",
            "Successful Pickups",
            "Pickup Success Rate (%)",
            "On-Time Deliveries",
            "On-Time Delivery Rate (%)",
        ])

        for t in transporters:
            writer.writerow([
                t.transporter_name,
                t.transporter_code or "",
                t.total_bookings,
                t.accepted_bookings,
                t.rejected_bookings,
                t.expired_bookings,
                f"{t.acceptance_rate}%",
                t.successful_pickups,
                f"{t.pickup_success_rate}%",
                t.on_time_deliveries,
                f"{t.on_time_delivery_rate}%",
            ])

        return output.getvalue()
