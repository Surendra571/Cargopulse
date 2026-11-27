import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import AssignmentStatus, BookingStatus, ShipmentStatus
from app.models.integrations import AIActionRecord, AuditLog
from app.models.shipment import Shipment, ShipmentAssignment, ShipmentEvent, TransporterBooking
from app.models.transporter import Driver, Transporter, TransporterServiceArea, Vehicle
from app.schemas.matching import (
    MatchedVehicleItem,
    MatchingAuditRecordResponse,
    ScorecardBreakdown,
    ScorecardComponent,
    TransporterMatchingResponse,
    TransporterRecommendationItem,
    TransporterSelectionRequest,
    TransporterSelectionResponse,
)


def _json_safe(data: Any) -> Any:
    """Recursively converts Decimals, UUIDs, and datetimes into JSON serializable values."""
    if isinstance(data, dict):
        return {k: _json_safe(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_json_safe(v) for v in data]
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, uuid.UUID):
        return str(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    return data


class MatchingService:
    """
    Intelligent Transporter Matching and Ranking Engine.
    Implements:
    - Step 1: Hard eligibility filters (Verification, Suspension, Vehicle Type/Capacity, Expirations, Route Coverage)
    - Step 2: Explainable scoring model with configurable weights (Pickup, On-Time, Acceptance, Route, Cost)
    - Step 3: Transparent audit logging via AIActionRecord
    - Step 4: Dispatch manager selection and booking creation
    """

    DEFAULT_WEIGHTS = {
        "pickup_reliability": 0.40,
        "ontime_delivery": 0.25,
        "booking_acceptance": 0.15,
        "route_suitability": 0.10,
        "cost_competitiveness": 0.10,
    }

    @classmethod
    async def match_transporters_for_shipment(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        shipment_id: uuid.UUID,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> TransporterMatchingResponse:
        """
        Evaluates and ranks all organization transporters for a target shipment.
        Deterministic and fully explainable without fabricating availability.
        """
        # 1. Fetch target shipment
        shipment_stmt = (
            select(Shipment)
            .where(
                Shipment.id == shipment_id,
                Shipment.organization_id == organization_id,
                Shipment.is_deleted == False,
            )
        )
        shipment = (await session.execute(shipment_stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found in your organization.",
            )

        weights = custom_weights or cls.DEFAULT_WEIGHTS

        # 2. Fetch all transporters for organization with vehicles and service areas
        transporters_stmt = (
            select(Transporter)
            .where(
                Transporter.organization_id == organization_id,
                Transporter.is_deleted == False,
            )
            .options(
                selectinload(Transporter.vehicles),
                selectinload(Transporter.service_areas),
                selectinload(Transporter.bookings),
            )
        )
        carriers = list((await session.execute(transporters_stmt)).scalars().all())

        now = datetime.now(timezone.utc)
        shipment_weight = float(shipment.total_weight_kg)
        meta = shipment.custom_metadata or {}
        shipment_vehicle_type = meta.get("required_vehicle_type") or "53' Dry Van"
        req_vehicle_type = shipment_vehicle_type.strip().lower()

        origin_city = (shipment.origin_city or "").strip().lower()
        origin_state = (shipment.origin_state or "").strip().lower()
        dest_city = (shipment.destination_city or "").strip().lower()
        dest_state = (shipment.destination_state or "").strip().lower()

        eligible_items: List[TransporterRecommendationItem] = []
        excluded_items: List[TransporterRecommendationItem] = []

        for carrier in carriers:
            compliance = carrier.compliance_details or {}
            verification_status = compliance.get("verification_status", "REGISTERED")
            is_active = carrier.is_active and compliance.get("account_status", "ACTIVE") != "SUSPENDED"

            ineligibility_reasons: List[str] = []

            # -------------------------------------------------------------
            # STEP 1: HARD ELIGIBILITY FILTERS
            # -------------------------------------------------------------

            # Filter 1: Verification status
            if verification_status != "VERIFIED":
                ineligibility_reasons.append(
                    f"Carrier verification is '{verification_status}' (must be VERIFIED to receive bookings)."
                )

            # Filter 2: Account active status / suspended
            if not is_active or verification_status == "SUSPENDED":
                ineligibility_reasons.append(
                    "Carrier account is currently suspended or deactivated from active dispatch."
                )

            # Filter 3: Route suitability check
            route_match_type, route_score, route_reason = cls._evaluate_route_suitability(
                carrier=carrier,
                origin_city=origin_city,
                origin_state=origin_state,
                dest_city=dest_city,
                dest_state=dest_state,
            )
            if route_score <= 0:
                ineligibility_reasons.append(
                    f"Carrier does not service corridor {shipment.origin_city}, {shipment.origin_state} -> {shipment.destination_city}, {shipment.destination_state}."
                )

            # Filter 4: Eligible vehicle capacity and non-expired documents
            eligible_vehicles = []
            for v in carrier.vehicles:
                if v.is_deleted or not v.is_available:
                    continue

                v_cap = float(v.capacity_kg)
                if v_cap < shipment_weight:
                    continue

                # Check vehicle type match
                v_type = (v.vehicle_type or "").strip().lower()
                if req_vehicle_type and req_vehicle_type not in v_type and v_type not in req_vehicle_type:
                    continue

                # Check document expirations
                if v.insurance_expiry and v.insurance_expiry.replace(tzinfo=timezone.utc) < now:
                    continue
                if v.fitness_expiry and v.fitness_expiry.replace(tzinfo=timezone.utc) < now:
                    continue

                eligible_vehicles.append(
                    MatchedVehicleItem(
                        id=str(v.id),
                        license_plate=v.license_plate,
                        vehicle_type=v.vehicle_type,
                        capacity_kg=v_cap,
                        volume_cbm=float(v.volume_cbm) if v.volume_cbm else None,
                        is_available=v.is_available,
                        insurance_expiry=v.insurance_expiry,
                        fitness_expiry=v.fitness_expiry,
                    )
                )

            if len(eligible_vehicles) == 0:
                ineligibility_reasons.append(
                    f"No available active vehicle with capacity >= {shipment_weight}kg matching type '{shipment_vehicle_type}' with valid documentation."
                )

            # -------------------------------------------------------------
            # STEP 2: SCORING & SCORECARD (for eligible & excluded transparency)
            # -------------------------------------------------------------
            scorecard, overall_score, is_new_carrier, explanation = cls._calculate_scorecard(
                carrier=carrier,
                route_score=route_score,
                route_reason=route_reason,
                weights=weights,
            )

            rec_item = TransporterRecommendationItem(
                transporter_id=str(carrier.id),
                transporter_name=carrier.name,
                transporter_code=carrier.code,
                phone=carrier.phone,
                email=carrier.email,
                gstin=carrier.gstin,
                verification_status=verification_status,
                account_status="ACTIVE" if is_active else "SUSPENDED",
                reliability_score=float(carrier.reliability_score),
                match_score=overall_score if len(ineligibility_reasons) == 0 else 0.0,
                rank=0,  # Will be assigned after sorting
                is_eligible=len(ineligibility_reasons) == 0,
                ineligibility_reasons=ineligibility_reasons,
                scorecard=scorecard,
                recommendation_summary=explanation,
                is_new_transporter=is_new_carrier,
                eligible_vehicles=eligible_vehicles,
                total_eligible_vehicles_count=len(eligible_vehicles),
                route_suitability_type=route_match_type,
                estimated_cost=cls._estimate_corridor_cost(shipment, route_match_type),
                currency="USD",
            )

            if len(ineligibility_reasons) == 0:
                eligible_items.append(rec_item)
            else:
                excluded_items.append(rec_item)

        # Sort eligible descending by match_score
        eligible_items.sort(key=lambda x: x.match_score, reverse=True)
        for idx, item in enumerate(eligible_items, start=1):
            item.rank = idx

        # Sort excluded by carrier name
        excluded_items.sort(key=lambda x: x.transporter_name)

        # -------------------------------------------------------------
        # STEP 3: AUDIT RECORD VIA AIActionRecord
        # -------------------------------------------------------------
        audit_record_response = None
        top_carrier = eligible_items[0] if len(eligible_items) > 0 else None
        top_score = top_carrier.match_score if top_carrier else 0.0

        prompt_summary = (
            f"Matching evaluation for Shipment {shipment.tracking_number} | "
            f"Lane: {shipment.origin_city}, {shipment.origin_state} -> {shipment.destination_city}, {shipment.destination_state} | "
            f"Cargo: {shipment.total_weight_kg}kg ({shipment_vehicle_type})"
        )
        decision_summary = (
            f"Evaluated {len(carriers)} carriers. Found {len(eligible_items)} eligible, {len(excluded_items)} excluded. "
            + (f"Top recommendation: {top_carrier.transporter_name} ({top_carrier.transporter_code}) with Score {top_score}." if top_carrier else "No eligible carriers found.")
        )

        ai_record = AIActionRecord(
            organization_id=organization_id,
            shipment_id=shipment.id,
            action_type="RANK_TRANSPORTERS",
            prompt_summary=prompt_summary,
            decision_summary=decision_summary,
            confidence_score=top_score / 100.0,
            requires_human_approval=True,
            raw_response={
                "eligible_count": len(eligible_items),
                "top_carrier_id": str(top_carrier.transporter_id) if top_carrier else None,
                "top_score": top_score,
                "weights": weights,
                "recommendations_summary": [
                    {
                        "rank": r.rank,
                        "name": r.transporter_name,
                        "score": r.match_score,
                        "eligible_vehicles": r.total_eligible_vehicles_count,
                    }
                    for r in eligible_items[:5]
                ],
            },
        )
        session.add(ai_record)
        await session.commit()
        await session.refresh(ai_record)

        audit_record_response = MatchingAuditRecordResponse(
            action_id=str(ai_record.id),
            action_type=ai_record.action_type,
            confidence_score=ai_record.confidence_score,
            decision_summary=ai_record.decision_summary,
            prompt_summary=ai_record.prompt_summary,
            requires_human_approval=ai_record.requires_human_approval,
            created_at=ai_record.created_at,
        )

        return TransporterMatchingResponse(
            shipment_id=str(shipment.id),
            tracking_number=shipment.tracking_number,
            origin_city=shipment.origin_city,
            origin_state=shipment.origin_state,
            destination_city=shipment.destination_city,
            destination_state=shipment.destination_state,
            total_weight_kg=float(shipment.total_weight_kg),
            required_vehicle_type=shipment_vehicle_type,
            scheduled_pickup_time=shipment.scheduled_pickup_time,
            expected_delivery_time=shipment.expected_delivery_time,
            total_carriers_evaluated=len(carriers),
            eligible_carriers_count=len(eligible_items),
            excluded_carriers_count=len(excluded_items),
            recommendations=eligible_items,
            excluded=excluded_items,
            weights_used=weights,
            audit_record=audit_record_response,
        )

    @classmethod
    def _evaluate_route_suitability(
        cls,
        carrier: Transporter,
        origin_city: str,
        origin_state: str,
        dest_city: str,
        dest_state: str,
    ) -> Tuple[str, float, str]:
        """
        Determines if a carrier serves the required corridor and computes route suitability score (0-100).
        """
        # 1. Dedicated service area lane check
        for sa in carrier.service_areas:
            if not sa.is_active:
                continue
            sa_orig = (sa.origin_region or "").lower()
            sa_dest = (sa.destination_region or "").lower()

            orig_match = origin_city in sa_orig or origin_state in sa_orig or sa_orig in origin_city or sa_orig in origin_state
            dest_match = dest_city in sa_dest or dest_state in sa_dest or sa_dest in dest_city or sa_dest in dest_state

            if orig_match and dest_match:
                return (
                    "DIRECT_LANE",
                    100.0,
                    f"Direct corridor mapped: {sa.origin_region} -> {sa.destination_region} (~{sa.estimated_transit_hours}h transit).",
                )

        # 2. Operating routes check
        compliance = carrier.compliance_details or {}
        routes = [r.lower() for r in compliance.get("operating_routes", [])]
        for r in routes:
            orig_in_route = origin_city in r or origin_state in r
            dest_in_route = dest_city in r or dest_state in r
            if orig_in_route and dest_in_route:
                return (
                    "OPERATING_CORRIDOR",
                    90.0,
                    f"Corridor listed in carrier primary operating routes: '{r}'.",
                )

        # 3. Service regions coverage check
        regions = [reg.lower() for reg in compliance.get("service_regions", [])]
        if len(regions) > 0:
            has_orig = any(origin_state in reg or origin_city in reg or reg in origin_state for reg in regions)
            has_dest = any(dest_state in reg or dest_city in reg or reg in dest_state for reg in regions)

            if has_orig and has_dest:
                return (
                    "REGIONAL_COVERAGE",
                    80.0,
                    f"Carrier has active operating hubs in both origin ({origin_state.upper()}) and destination ({dest_state.upper()}) territories.",
                )
            elif has_orig or has_dest:
                return (
                    "PARTIAL_REGIONAL",
                    65.0,
                    f"Carrier has regional presence in {'origin' if has_orig else 'destination'} region.",
                )

        # 4. If carrier has no restrictive regions listed, treat as broad general carrier
        if len(regions) == 0 and len(routes) == 0 and len(carrier.service_areas) == 0:
            return (
                "GENERAL",
                50.0,
                "National / unconstrained carrier profile without designated exclusive corridors.",
            )

        # No match found
        return ("NO_COVERAGE", 0.0, "Route not serviced by carrier.")

    @classmethod
    def _calculate_scorecard(
        cls,
        carrier: Transporter,
        route_score: float,
        route_reason: str,
        weights: Dict[str, float],
    ) -> Tuple[ScorecardBreakdown, float, bool, str]:
        """
        Calculates explainable weighted scorecard and transparent reasoning.
        Gracefully handles new carriers without historical data using neutral smoothing.
        """
        is_new_carrier = carrier.total_deliveries < 3

        # 1. Pickup Reliability (Weight: 40%)
        w_pickup = weights.get("pickup_reliability", 0.40)
        if is_new_carrier:
            s_pickup = 75.0
            exp_pickup = "New carrier baseline prior (75.0%): Insufficient completed deliveries (< 3 trips)."
        else:
            s_pickup = float(carrier.reliability_score)
            exp_pickup = f"Historical pickup fulfillment score: {s_pickup:.1f}% based on {carrier.total_deliveries} completed trips."

        # 2. On-Time Delivery (Weight: 25%)
        w_ontime = weights.get("ontime_delivery", 0.25)
        if is_new_carrier or carrier.total_deliveries == 0:
            s_ontime = 75.0
            exp_ontime = "New carrier baseline prior (75.0%): Pending delivery completion track record."
        else:
            s_ontime = (float(carrier.on_time_deliveries) / float(carrier.total_deliveries)) * 100.0
            exp_ontime = f"Historical on-time delivery rate: {s_ontime:.1f}% ({carrier.on_time_deliveries}/{carrier.total_deliveries} trips)."

        # 3. Booking Acceptance (Weight: 15%)
        w_accept = weights.get("booking_acceptance", 0.15)
        bookings = carrier.bookings or []
        if len(bookings) == 0:
            s_accept = 80.0
            exp_accept = "New partner baseline prior (80.0%): No prior dispatch tenders issued."
        else:
            accepted_cnt = sum(1 for b in bookings if b.status == BookingStatus.ACCEPTED)
            total_tenders = len(bookings)
            s_accept = (float(accepted_cnt) / float(total_tenders)) * 100.0
            exp_accept = f"Dispatch tender acceptance rate: {s_accept:.1f}% ({accepted_cnt}/{total_tenders} tenders accepted)."

        # 4. Route Suitability (Weight: 10%)
        w_route = weights.get("route_suitability", 0.10)
        s_route = route_score
        exp_route = route_reason

        # 5. Cost Competitiveness (Weight: 10%)
        w_cost = weights.get("cost_competitiveness", 0.10)
        s_cost = 75.0
        exp_cost = "Standard organization contracted tariff tier (Benchmark score 75.0)."

        # Weighted calculation
        c_pickup = ScorecardComponent(
            score=round(s_pickup, 1),
            weight=w_pickup,
            weighted_score=round(s_pickup * w_pickup, 2),
            explanation=exp_pickup,
        )
        c_ontime = ScorecardComponent(
            score=round(s_ontime, 1),
            weight=w_ontime,
            weighted_score=round(s_ontime * w_ontime, 2),
            explanation=exp_ontime,
        )
        c_accept = ScorecardComponent(
            score=round(s_accept, 1),
            weight=w_accept,
            weighted_score=round(s_accept * w_accept, 2),
            explanation=exp_accept,
        )
        c_route = ScorecardComponent(
            score=round(s_route, 1),
            weight=w_route,
            weighted_score=round(s_route * w_route, 2),
            explanation=exp_route,
        )
        c_cost = ScorecardComponent(
            score=round(s_cost, 1),
            weight=w_cost,
            weighted_score=round(s_cost * w_cost, 2),
            explanation=exp_cost,
        )

        overall = round(
            c_pickup.weighted_score
            + c_ontime.weighted_score
            + c_accept.weighted_score
            + c_route.weighted_score
            + c_cost.weighted_score,
            1,
        )

        scorecard = ScorecardBreakdown(
            pickup_reliability=c_pickup,
            ontime_delivery=c_ontime,
            booking_acceptance=c_accept,
            route_suitability=c_route,
            cost_competitiveness=c_cost,
        )

        if is_new_carrier:
            overall_summary = f"New partner (Baseline score {overall}). Qualified fleet capacity and route compatibility confirmed."
        else:
            overall_summary = (
                f"Established partner with {s_pickup:.0f}% pickup adherence, {s_ontime:.0f}% on-time completion, "
                f"and {route_reason.lower()}"
            )

        return scorecard, overall, is_new_carrier, overall_summary

    @classmethod
    def _estimate_corridor_cost(cls, shipment: Shipment, route_type: str) -> Optional[float]:
        """Provides estimated freight cost when standard tariff benchmarks apply."""
        weight = float(shipment.total_weight_kg)
        base_rate = 850.0 if weight < 10000 else 1450.0
        if route_type == "DIRECT_LANE":
            return round(base_rate * 0.95, 2)
        elif route_type == "OPERATING_CORRIDOR":
            return round(base_rate * 1.0, 2)
        elif route_type == "REGIONAL_COVERAGE":
            return round(base_rate * 1.1, 2)
        return round(base_rate * 1.15, 2)

    @classmethod
    async def select_transporter_for_shipment(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        shipment_id: uuid.UUID,
        data: TransporterSelectionRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TransporterSelectionResponse:
        """
        Step 4: Dispatch Manager manually selects and commits an eligible transporter to a shipment.
        Creates TransporterBooking, updates Shipment assignment, records audit trail and AIActionRecord approval.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch Shipment
        shipment_stmt = (
            select(Shipment)
            .where(
                Shipment.id == shipment_id,
                Shipment.organization_id == organization_id,
                Shipment.is_deleted == False,
            )
        )
        shipment = (await session.execute(shipment_stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found in your organization.",
            )

        # Enforce dispatch eligibility
        if shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.PENDING_ACCEPTANCE]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign transporter to shipment in status '{shipment.status.value}'. Shipment must be in DRAFT or PENDING_ACCEPTANCE.",
            )

        # 2. Fetch and Validate Transporter
        transporter_stmt = (
            select(Transporter)
            .where(
                Transporter.id == data.transporter_id,
                Transporter.organization_id == organization_id,
                Transporter.is_deleted == False,
            )
        )
        transporter = (await session.execute(transporter_stmt)).scalar_one_or_none()
        if not transporter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected transporter not found in your organization.",
            )

        compliance = transporter.compliance_details or {}
        verification_status = compliance.get("verification_status", "REGISTERED")
        if verification_status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transporter '{transporter.name}' is {verification_status} and cannot be assigned to active shipments. Must be VERIFIED.",
            )
        if not transporter.is_active or compliance.get("account_status", "ACTIVE") == "SUSPENDED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transporter '{transporter.name}' is suspended or deactivated.",
            )

        # 3. Create TransporterBooking
        booking = TransporterBooking(
            organization_id=organization_id,
            shipment_id=shipment.id,
            transporter_id=transporter.id,
            status=BookingStatus.REQUESTED,
            offered_rate=Decimal(str(data.agreed_rate)) if data.agreed_rate is not None else None,
            agreed_rate=Decimal(str(data.agreed_rate)) if data.agreed_rate is not None else None,
            expires_at=now + timedelta(hours=24),
            response_notes=data.booking_notes,
        )
        session.add(booking)
        await session.flush()

        # 4. Update Shipment
        meta = dict(shipment.custom_metadata or {})
        meta["assigned_transporter_id"] = str(transporter.id)
        meta["assigned_transporter_name"] = transporter.name
        shipment.custom_metadata = meta
        shipment.status = ShipmentStatus.PENDING_ACCEPTANCE
        shipment.updated_at = now

        # 5. Optional Vehicle & Driver ShipmentAssignment
        assignment_id = None
        if data.vehicle_id and data.driver_id:
            # Validate vehicle belongs to carrier and organization
            v_stmt = select(Vehicle).where(
                Vehicle.id == data.vehicle_id,
                Vehicle.transporter_id == transporter.id,
                Vehicle.organization_id == organization_id,
                Vehicle.is_deleted == False,
            )
            v_rec = (await session.execute(v_stmt)).scalar_one_or_none()
            if not v_rec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified vehicle does not belong to the selected carrier.",
                )

            # Validate driver belongs to carrier and organization
            d_stmt = select(Driver).where(
                Driver.id == data.driver_id,
                Driver.transporter_id == transporter.id,
                Driver.organization_id == organization_id,
                Driver.is_deleted == False,
            )
            d_rec = (await session.execute(d_stmt)).scalar_one_or_none()
            if not d_rec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified driver does not belong to the selected carrier.",
                )

            assignment = ShipmentAssignment(
                organization_id=organization_id,
                shipment_id=shipment.id,
                vehicle_id=v_rec.id,
                driver_id=d_rec.id,
                status=AssignmentStatus.ASSIGNED,
                assigned_at=now,
            )
            session.add(assignment)
            await session.flush()
            assignment_id = str(assignment.id)

        # 6. Append ShipmentEvent
        event = ShipmentEvent(
            organization_id=organization_id,
            shipment_id=shipment.id,
            event_type="TRANSPORTER_SELECTED",
            description=f"Transporter '{transporter.name}' ({transporter.code}) selected by Dispatch Manager.",
            location_name=f"{shipment.origin_city}, {shipment.origin_state}",
            source="DISPATCH_MANAGER_MANUAL_SELECTION",
            created_by_user_id=user_id,
            occurred_at=now,
            payload={
                "transporter_id": str(transporter.id),
                "transporter_code": transporter.code,
                "booking_id": str(booking.id),
                "agreed_rate": float(data.agreed_rate) if data.agreed_rate is not None else None,
                "assignment_id": assignment_id,
            },
        )
        session.add(event)

        # 7. Update latest AIActionRecord for this shipment
        ai_stmt = (
            select(AIActionRecord)
            .where(
                AIActionRecord.shipment_id == shipment.id,
                AIActionRecord.organization_id == organization_id,
                AIActionRecord.action_type == "RANK_TRANSPORTERS",
            )
            .order_by(desc(AIActionRecord.created_at))
            .limit(1)
        )
        latest_ai_record = (await session.execute(ai_stmt)).scalar_one_or_none()
        if latest_ai_record:
            latest_ai_record.approved_by_user_id = user_id
            latest_ai_record.approved_at = now

        # 8. Record AuditLog
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="TRANSPORTER_MANUAL_SELECTION",
            entity_name="Shipment",
            entity_id=shipment.id,
            ip_address=ip_address,
            user_agent=user_agent,
            changes=_json_safe({
                "transporter_id": str(transporter.id),
                "transporter_name": transporter.name,
                "transporter_code": transporter.code,
                "booking_id": str(booking.id),
                "shipment_status": shipment.status.value,
                "agreed_rate": float(data.agreed_rate) if data.agreed_rate is not None else None,
            }),
            created_at=now,
        )
        session.add(audit)
        await session.commit()

        return TransporterSelectionResponse(
            success=True,
            message=f"Transporter '{transporter.name}' successfully selected and booking tender created.",
            shipment_id=str(shipment.id),
            tracking_number=shipment.tracking_number,
            transporter_id=str(transporter.id),
            transporter_name=transporter.name,
            transporter_code=transporter.code,
            booking_id=str(booking.id),
            assignment_id=assignment_id,
            shipment_status=shipment.status.value,
            agreed_rate=data.agreed_rate,
            audit_log_id=str(audit.id),
            selected_at=now,
        )
