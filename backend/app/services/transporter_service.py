import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, cast, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.enums import BookingStatus
from app.models.integrations import AuditLog
from app.models.shipment import Shipment, TransporterBooking
from app.models.transporter import Driver, Transporter, TransporterServiceArea, Vehicle
from app.schemas.transporter import (
    DriverAssignmentRequest,
    DriverCreateRequest,
    DriverListItem,
    DriverUpdateRequest,
    PaginatedDriversResponse,
    PaginatedTransportersResponse,
    PaginatedVehiclesResponse,
    ServiceAreaCreateRequest,
    ServiceAreaResponse,
    TransporterBookingSummaryItem,
    TransporterCreateRequest,
    TransporterDetailResponse,
    TransporterDocumentItem,
    TransporterDocumentUploadRequest,
    TransporterListItem,
    TransporterPerformanceSummary,
    TransporterUpdateRequest,
    TransporterVerificationRequest,
    TransporterVerificationStatus,
    VehicleCreateRequest,
    VehicleListItem,
    VehicleUpdateRequest,
)


def _json_safe(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (datetime, uuid.UUID)):
        return str(val)
    if hasattr(val, "__float__"):
        return float(val)
    return val


def _mask_license(license_no: Optional[str]) -> str:
    if not license_no or len(license_no) <= 4:
        return license_no or "N/A"
    visible = license_no[-4:]
    masked = "*" * (len(license_no) - 4)
    return f"{masked}{visible}"


class TransporterService:

    # =========================================================================
    # TRANSPORTER METHODS
    # =========================================================================

    @staticmethod
    async def create_transporter(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TransporterCreateRequest,
    ) -> TransporterListItem:
        """
        Registers a new transporter partner for the organization with initial
        'REGISTERED' status and complete contact/service profiles.
        """
        # Auto-generate carrier code if not supplied
        code = data.code
        if not code:
            clean_name = "".join(c for c in data.name.upper() if c.isalnum())[:4] or "TRP"
            code = f"{clean_name}-{uuid.uuid4().hex[:5].upper()}"

        # Check duplicate code within the organization
        existing_code_stmt = select(Transporter).where(
            and_(
                Transporter.organization_id == organization_id,
                Transporter.code == code,
                Transporter.is_deleted.is_(False),
            )
        )
        if (await session.execute(existing_code_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A transporter with code '{code}' already exists in your organization.",
            )

        # Build initial compliance details
        compliance_meta = {
            "verification_status": TransporterVerificationStatus.REGISTERED,
            "verification_notes": "Initial partner registration.",
            "verified_at": None,
            "verified_by_user": None,
            "service_regions": data.service_regions,
            "operating_routes": data.operating_routes,
            "vehicle_categories": data.vehicle_categories,
            "max_cargo_capacity_kg": data.max_cargo_capacity_kg,
            "documents": [],
            "assigned_vehicle_mappings": {},
        }

        transporter_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        transporter = Transporter(
            id=transporter_id,
            organization_id=organization_id,
            name=data.name,
            code=code,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
            gstin=data.gstin,
            is_active=True,
            reliability_score=100.0,
            total_deliveries=0,
            on_time_deliveries=0,
            compliance_details=compliance_meta,
            created_at=now,
            updated_at=now,
        )
        session.add(transporter)

        # Seed initial service areas if provided
        for route_str in data.operating_routes:
            if "->" in route_str:
                parts = [p.strip() for p in route_str.split("->", 1)]
                sa = TransporterServiceArea(
                    id=uuid.uuid4(),
                    transporter_id=transporter_id,
                    origin_region=parts[0],
                    destination_region=parts[1],
                    estimated_transit_hours=24,
                    is_active=True,
                )
                session.add(sa)

        # Audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE",
            entity_name="Transporter",
            entity_id=transporter_id,
            changes={
                "name": data.name,
                "code": code,
                "verification_status": TransporterVerificationStatus.REGISTERED,
            },
        )
        session.add(audit)

        await session.commit()
        return await TransporterService.get_transporter_list_item(session, organization_id, transporter_id)

    @staticmethod
    async def get_transporter_list_item(
        session: AsyncSession,
        organization_id: uuid.UUID,
        transporter_id: uuid.UUID,
    ) -> TransporterListItem:
        stmt = (
            select(
                Transporter,
                func.count(Vehicle.id).filter(Vehicle.is_deleted.is_(False)).label("total_vehicles"),
                func.count(Vehicle.id).filter(and_(Vehicle.is_deleted.is_(False), Vehicle.is_available.is_(True))).label("active_vehicles"),
                func.count(Driver.id).filter(Driver.is_deleted.is_(False)).label("total_drivers"),
                func.count(Driver.id).filter(and_(Driver.is_deleted.is_(False), Driver.is_available.is_(True))).label("active_drivers"),
            )
            .outerjoin(Vehicle, Vehicle.transporter_id == Transporter.id)
            .outerjoin(Driver, Driver.transporter_id == Transporter.id)
            .where(
                and_(
                    Transporter.id == transporter_id,
                    Transporter.organization_id == organization_id,
                    Transporter.is_deleted.is_(False),
                )
            )
            .group_by(Transporter.id)
        )
        row = (await session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        t, total_v, active_v, total_d, active_d = row
        meta = t.compliance_details or {}
        v_status = meta.get("verification_status", TransporterVerificationStatus.REGISTERED)
        account_status = "ACTIVE" if t.is_active else "SUSPENDED" if v_status == "SUSPENDED" else "INACTIVE"
        on_time_rate = (t.on_time_deliveries / t.total_deliveries * 100.0) if t.total_deliveries > 0 else 100.0

        return TransporterListItem(
            id=str(t.id),
            organization_id=str(t.organization_id),
            name=t.name,
            code=t.code,
            contact_person=t.contact_person,
            phone=t.phone,
            email=t.email,
            gstin=t.gstin,
            is_active=t.is_active,
            account_status=account_status,
            verification_status=v_status,
            reliability_score=float(t.reliability_score),
            total_deliveries=t.total_deliveries,
            on_time_deliveries=t.on_time_deliveries,
            on_time_delivery_rate=round(on_time_rate, 1),
            total_vehicles=total_v or 0,
            active_vehicles=active_v or 0,
            total_drivers=total_d or 0,
            active_drivers=active_d or 0,
            service_regions=meta.get("service_regions", []),
            vehicle_categories=meta.get("vehicle_categories", []),
            max_cargo_capacity_kg=meta.get("max_cargo_capacity_kg"),
            created_at=t.created_at,
        )

    @staticmethod
    async def list_transporters(
        session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        verification_status: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> PaginatedTransportersResponse:
        """
        Lists tenant transporters with search, status filters, fleet counts, and pagination.
        """
        filters = [
            Transporter.organization_id == organization_id,
            Transporter.is_deleted.is_(False),
        ]

        if is_active is not None:
            filters.append(Transporter.is_active.is_(is_active))

        if verification_status and verification_status.upper() != "ALL":
            filters.append(
                Transporter.compliance_details["verification_status"].astext == verification_status.upper()
            )

        if search:
            s_term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Transporter.name.ilike(s_term),
                    Transporter.code.ilike(s_term),
                    Transporter.contact_person.ilike(s_term),
                    Transporter.phone.ilike(s_term),
                    Transporter.email.ilike(s_term),
                    Transporter.gstin.ilike(s_term),
                    cast(Transporter.compliance_details["service_regions"], String).ilike(s_term),
                )
            )

        # Count total
        count_stmt = select(func.count(Transporter.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        offset = (page - 1) * page_size

        # Fetch records
        stmt = (
            select(
                Transporter,
                func.count(func.distinct(Vehicle.id)).filter(Vehicle.is_deleted.is_(False)).label("total_vehicles"),
                func.count(func.distinct(Vehicle.id)).filter(and_(Vehicle.is_deleted.is_(False), Vehicle.is_available.is_(True))).label("active_vehicles"),
                func.count(func.distinct(Driver.id)).filter(Driver.is_deleted.is_(False)).label("total_drivers"),
                func.count(func.distinct(Driver.id)).filter(and_(Driver.is_deleted.is_(False), Driver.is_available.is_(True))).label("active_drivers"),
            )
            .outerjoin(Vehicle, Vehicle.transporter_id == Transporter.id)
            .outerjoin(Driver, Driver.transporter_id == Transporter.id)
            .where(and_(*filters))
            .group_by(Transporter.id)
            .order_by(desc(Transporter.created_at))
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).all()

        items = []
        for t, total_v, active_v, total_d, active_d in rows:
            meta = t.compliance_details or {}
            v_status = meta.get("verification_status", TransporterVerificationStatus.REGISTERED)
            account_status = "ACTIVE" if t.is_active else "SUSPENDED" if v_status == "SUSPENDED" else "INACTIVE"
            on_time_rate = (t.on_time_deliveries / t.total_deliveries * 100.0) if t.total_deliveries > 0 else 100.0

            items.append(
                TransporterListItem(
                    id=str(t.id),
                    organization_id=str(t.organization_id),
                    name=t.name,
                    code=t.code,
                    contact_person=t.contact_person,
                    phone=t.phone,
                    email=t.email,
                    gstin=t.gstin,
                    is_active=t.is_active,
                    account_status=account_status,
                    verification_status=v_status,
                    reliability_score=float(t.reliability_score),
                    total_deliveries=t.total_deliveries,
                    on_time_deliveries=t.on_time_deliveries,
                    on_time_delivery_rate=round(on_time_rate, 1),
                    total_vehicles=total_v or 0,
                    active_vehicles=active_v or 0,
                    total_drivers=total_d or 0,
                    active_drivers=active_d or 0,
                    service_regions=meta.get("service_regions", []),
                    vehicle_categories=meta.get("vehicle_categories", []),
                    max_cargo_capacity_kg=meta.get("max_cargo_capacity_kg"),
                    created_at=t.created_at,
                )
            )

        return PaginatedTransportersResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def get_transporter_detail(
        session: AsyncSession,
        organization_id: uuid.UUID,
        transporter_id: uuid.UUID,
    ) -> Optional[TransporterDetailResponse]:
        """
        Retrieves full carrier operational profile with eager-loaded fleet vehicles,
        verified drivers, lanes, recent bookings, compliance documents, and performance.
        Enforces tenant isolation (IDOR protection).
        """
        stmt = (
            select(Transporter)
            .options(
                selectinload(Transporter.vehicles),
                selectinload(Transporter.drivers),
                selectinload(Transporter.service_areas),
                selectinload(Transporter.bookings).selectinload(TransporterBooking.shipment),
            )
            .where(
                and_(
                    Transporter.id == transporter_id,
                    Transporter.organization_id == organization_id,
                    Transporter.is_deleted.is_(False),
                )
            )
        )
        t = (await session.execute(stmt)).scalar_one_or_none()
        if not t:
            return None

        meta = t.compliance_details or {}
        now = datetime.now(timezone.utc)
        driver_mappings = meta.get("assigned_vehicle_mappings", {})

        # Vehicles mapping
        vehicle_items = []
        total_fleet_cap = 0.0
        for v in t.vehicles:
            if v.is_deleted:
                continue
            cap = float(v.capacity_kg)
            total_fleet_cap += cap

            # Check expired docs
            has_expired = False
            if v.insurance_expiry and v.insurance_expiry < now:
                has_expired = True
            if v.fitness_expiry and v.fitness_expiry < now:
                has_expired = True

            v_status = "EXPIRED_DOCUMENTS" if has_expired else "ACTIVE" if v.is_available else "MAINTENANCE"

            # Check assigned driver
            driver_name = None
            assigned_d_id = None
            for d_id_str, v_id_str in driver_mappings.items():
                if v_id_str == str(v.id):
                    for d in t.drivers:
                        if str(d.id) == d_id_str:
                            driver_name = f"{d.first_name} {d.last_name}"
                            assigned_d_id = str(d.id)
                            break

            vehicle_items.append(
                VehicleListItem(
                    id=str(v.id),
                    transporter_id=str(t.id),
                    transporter_name=t.name,
                    license_plate=v.license_plate,
                    vehicle_type=v.vehicle_type,
                    capacity_kg=cap,
                    volume_cbm=float(v.volume_cbm) if v.volume_cbm else None,
                    is_available=v.is_available,
                    status=v_status,
                    has_expired_documents=has_expired,
                    insurance_expiry=v.insurance_expiry,
                    fitness_expiry=v.fitness_expiry,
                    rc_number=v.rc_number,
                    telematics_device_id=v.telematics_device_id,
                    assigned_driver_id=assigned_d_id,
                    assigned_driver_name=driver_name,
                    created_at=v.created_at,
                )
            )

        # Drivers mapping
        driver_items = []
        for d in t.drivers:
            if d.is_deleted:
                continue

            is_lic_expired = bool(d.license_expiry and d.license_expiry < now)
            d_status = "EXPIRED_LICENSE" if is_lic_expired else "ACTIVE" if d.is_available else "OFF_DUTY"

            assigned_v_id = driver_mappings.get(str(d.id))
            assigned_v_plate = None
            if assigned_v_id:
                for v in t.vehicles:
                    if str(v.id) == assigned_v_id:
                        assigned_v_plate = v.license_plate
                        break

            driver_items.append(
                DriverListItem(
                    id=str(d.id),
                    transporter_id=str(t.id),
                    transporter_name=t.name,
                    first_name=d.first_name,
                    last_name=d.last_name,
                    full_name=f"{d.first_name} {d.last_name}",
                    phone=d.phone,
                    license_number=d.license_number,
                    license_number_masked=_mask_license(d.license_number),
                    license_expiry=d.license_expiry,
                    is_license_expired=is_lic_expired,
                    is_available=d.is_available,
                    status=d_status,
                    assigned_vehicle_id=assigned_v_id,
                    assigned_vehicle_plate=assigned_v_plate,
                    created_at=d.created_at,
                )
            )

        # Service areas
        service_areas = [
            ServiceAreaResponse(
                id=str(sa.id),
                transporter_id=str(sa.transporter_id),
                origin_region=sa.origin_region,
                destination_region=sa.destination_region,
                origin_postal_code_prefix=sa.origin_postal_code_prefix,
                destination_postal_code_prefix=sa.destination_postal_code_prefix,
                estimated_transit_hours=sa.estimated_transit_hours,
                is_active=sa.is_active,
                created_at=sa.created_at,
            )
            for sa in t.service_areas
            if sa.is_active
        ]

        # Recent Bookings
        accepted_cnt = 0
        rejected_cnt = 0
        recent_bookings = []
        for bk in sorted(t.bookings, key=lambda x: x.created_at, reverse=True)[:10]:
            if bk.status == BookingStatus.ACCEPTED:
                accepted_cnt += 1
            elif bk.status == BookingStatus.REJECTED:
                rejected_cnt += 1

            shp_ref = bk.shipment.tracking_number if bk.shipment else "N/A"
            orig_sum = f"{bk.shipment.origin_city}, {bk.shipment.origin_state}" if bk.shipment else "Origin"
            dest_sum = f"{bk.shipment.destination_city}, {bk.shipment.destination_state}" if bk.shipment else "Destination"

            recent_bookings.append(
                TransporterBookingSummaryItem(
                    id=str(bk.id),
                    shipment_id=str(bk.shipment_id),
                    shipment_tracking_number=shp_ref,
                    origin_summary=orig_sum,
                    destination_summary=dest_sum,
                    status=bk.status.value if hasattr(bk.status, "value") else str(bk.status),
                    offered_rate=float(bk.offered_rate) if bk.offered_rate else None,
                    agreed_rate=float(bk.agreed_rate) if bk.agreed_rate else None,
                    created_at=bk.created_at,
                )
            )

        # Performance summary
        on_time_rate = (t.on_time_deliveries / t.total_deliveries * 100.0) if t.total_deliveries > 0 else 100.0
        perf = TransporterPerformanceSummary(
            reliability_score=float(t.reliability_score),
            total_deliveries=t.total_deliveries,
            on_time_deliveries=t.on_time_deliveries,
            on_time_rate=round(on_time_rate, 1),
            active_exceptions=0,
            accepted_bookings_count=accepted_cnt,
            rejected_bookings_count=rejected_cnt,
            total_fleet_capacity_kg=round(total_fleet_cap, 2),
        )

        # Compliance documents
        raw_docs = meta.get("documents", [])
        doc_items = [
            TransporterDocumentItem(
                doc_type=d.get("doc_type", "GENERAL"),
                document_number=d.get("document_number"),
                file_url=d.get("file_url", ""),
                expiry_date=datetime.fromisoformat(d["expiry_date"]) if d.get("expiry_date") else None,
                submitted_at=datetime.fromisoformat(d["submitted_at"]) if d.get("submitted_at") else t.created_at,
                status=d.get("status", "VERIFIED"),
            )
            for d in raw_docs
        ]

        v_status = meta.get("verification_status", TransporterVerificationStatus.REGISTERED)
        account_status = "ACTIVE" if t.is_active else "SUSPENDED" if v_status == "SUSPENDED" else "INACTIVE"

        return TransporterDetailResponse(
            id=str(t.id),
            organization_id=str(t.organization_id),
            name=t.name,
            code=t.code,
            contact_person=t.contact_person,
            phone=t.phone,
            email=t.email,
            gstin=t.gstin,
            is_active=t.is_active,
            account_status=account_status,
            verification_status=v_status,
            verification_notes=meta.get("verification_notes"),
            verified_at=datetime.fromisoformat(meta["verified_at"]) if meta.get("verified_at") else None,
            verified_by_user=meta.get("verified_by_user"),
            service_regions=meta.get("service_regions", []),
            operating_routes=meta.get("operating_routes", []),
            vehicle_categories=meta.get("vehicle_categories", []),
            max_cargo_capacity_kg=meta.get("max_cargo_capacity_kg"),
            documents=doc_items,
            vehicles=vehicle_items,
            drivers=driver_items,
            service_areas=service_areas,
            recent_bookings=recent_bookings,
            performance=perf,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )

    @staticmethod
    async def update_transporter(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        transporter_id: uuid.UUID,
        data: TransporterUpdateRequest,
    ) -> TransporterDetailResponse:
        """
        Updates basic profile and service region metadata for a transporter.
        """
        stmt = select(Transporter).where(
            and_(
                Transporter.id == transporter_id,
                Transporter.organization_id == organization_id,
                Transporter.is_deleted.is_(False),
            )
        )
        t = (await session.execute(stmt)).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        old_vals = {}
        new_vals = {}
        meta = dict(t.compliance_details or {})

        direct_fields = ["name", "contact_person", "phone", "email", "gstin", "is_active"]
        update_dict = data.model_dump(exclude_unset=True)

        for f in direct_fields:
            if f in update_dict:
                val = getattr(data, f)
                old_val = getattr(t, f)
                if old_val != val:
                    old_vals[f] = _json_safe(old_val)
                    new_vals[f] = _json_safe(val)
                    setattr(t, f, val)

        # Metadata fields
        meta_fields = ["service_regions", "operating_routes", "vehicle_categories", "max_cargo_capacity_kg"]
        for mf in meta_fields:
            if mf in update_dict:
                val = getattr(data, mf)
                old_val = meta.get(mf)
                if old_val != val:
                    old_vals[mf] = old_val
                    new_vals[mf] = val
                    meta[mf] = val

        t.compliance_details = meta
        t.updated_at = datetime.now(timezone.utc)

        if new_vals:
            audit = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                user_id=user_id,
                action="UPDATE",
                entity_name="Transporter",
                entity_id=transporter_id,
                changes={"old": old_vals, "new": new_vals},
            )
            session.add(audit)

        await session.commit()
        return await TransporterService.get_transporter_detail(session, organization_id, transporter_id)

    @staticmethod
    async def verify_transporter(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        transporter_id: uuid.UUID,
        data: TransporterVerificationRequest,
    ) -> TransporterDetailResponse:
        """
        Transitions carrier verification status (e.g. REGISTERED -> DOCUMENTS_SUBMITTED ->
        UNDER_VERIFICATION -> VERIFIED / REJECTED / SUSPENDED).
        Unverified transporters are barred from receiving active load bookings.
        """
        stmt = select(Transporter).where(
            and_(
                Transporter.id == transporter_id,
                Transporter.organization_id == organization_id,
                Transporter.is_deleted.is_(False),
            )
        )
        t = (await session.execute(stmt)).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        meta = dict(t.compliance_details or {})
        old_status = meta.get("verification_status", TransporterVerificationStatus.REGISTERED)
        new_status = data.status.upper()

        now = datetime.now(timezone.utc)
        meta["verification_status"] = new_status
        meta["verification_notes"] = data.verification_notes or f"Status changed to {new_status}"

        # Fetch verifier user email
        verifier = await session.get(User, user_id)
        verifier_email = verifier.email if verifier else str(user_id)

        if new_status == TransporterVerificationStatus.VERIFIED:
            meta["verified_at"] = now.isoformat()
            meta["verified_by_user"] = verifier_email
            t.is_active = True
        elif new_status == TransporterVerificationStatus.SUSPENDED:
            t.is_active = False

        t.compliance_details = meta
        t.updated_at = now

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="VERIFY",
            entity_name="Transporter",
            entity_id=transporter_id,
            changes={
                "old": {"verification_status": old_status},
                "new": {
                    "verification_status": new_status,
                    "notes": data.verification_notes,
                    "verified_by": verifier_email,
                },
            },
        )
        session.add(audit)

        await session.commit()
        return await TransporterService.get_transporter_detail(session, organization_id, transporter_id)

    @staticmethod
    async def suspend_transporter(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        transporter_id: uuid.UUID,
        reason: str,
    ) -> TransporterDetailResponse:
        """
        Immediately suspends a transporter. Suspended transporters cannot receive or
        accept new bookings or transport assignments.
        """
        return await TransporterService.verify_transporter(
            session=session,
            organization_id=organization_id,
            user_id=user_id,
            transporter_id=transporter_id,
            data=TransporterVerificationRequest(
                status=TransporterVerificationStatus.SUSPENDED,
                verification_notes=f"Carrier account suspended: {reason}",
            ),
        )

    @staticmethod
    async def upload_transporter_document(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        transporter_id: uuid.UUID,
        data: TransporterDocumentUploadRequest,
    ) -> TransporterDetailResponse:
        """
        Records a mandatory regulatory compliance document (insurance, motor carrier permit, tax certificate).
        Automatically transitions REGISTERED partner to DOCUMENTS_SUBMITTED.
        """
        stmt = select(Transporter).where(
            and_(
                Transporter.id == transporter_id,
                Transporter.organization_id == organization_id,
                Transporter.is_deleted.is_(False),
            )
        )
        t = (await session.execute(stmt)).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        meta = dict(t.compliance_details or {})
        docs = list(meta.get("documents", []))
        now = datetime.now(timezone.utc)

        doc_item = {
            "doc_type": data.doc_type,
            "document_number": data.document_number,
            "file_url": data.file_url,
            "expiry_date": data.expiry_date.isoformat() if data.expiry_date else None,
            "submitted_at": now.isoformat(),
            "status": "PENDING_VERIFICATION",
        }
        docs.append(doc_item)
        meta["documents"] = docs

        # Auto-promote to DOCUMENTS_SUBMITTED if newly registered
        if meta.get("verification_status") == TransporterVerificationStatus.REGISTERED:
            meta["verification_status"] = TransporterVerificationStatus.DOCUMENTS_SUBMITTED

        t.compliance_details = meta
        t.updated_at = now

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="UPLOAD_DOCUMENT",
            entity_name="Transporter",
            entity_id=transporter_id,
            changes={"doc_type": data.doc_type, "document_number": data.document_number},
        )
        session.add(audit)

        await session.commit()
        return await TransporterService.get_transporter_detail(session, organization_id, transporter_id)

    # =========================================================================
    # VEHICLE METHODS
    # =========================================================================

    @staticmethod
    async def create_vehicle(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: VehicleCreateRequest,
    ) -> VehicleListItem:
        """
        Registers a new commercial fleet vehicle under a carrier.
        Enforces unique license plate within the organization.
        """
        # Verify transporter belongs to org and is not deleted
        t = await session.get(Transporter, data.transporter_id)
        if not t or t.organization_id != organization_id or t.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        # Check duplicate license plate in organization
        clean_plate = data.license_plate.strip().upper()
        existing_plate_stmt = select(Vehicle).where(
            and_(
                Vehicle.organization_id == organization_id,
                Vehicle.license_plate == clean_plate,
                Vehicle.is_deleted.is_(False),
            )
        )
        if (await session.execute(existing_plate_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle with license plate '{clean_plate}' is already registered in your organization.",
            )

        vehicle_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        vehicle = Vehicle(
            id=vehicle_id,
            organization_id=organization_id,
            transporter_id=data.transporter_id,
            license_plate=clean_plate,
            vehicle_type=data.vehicle_type,
            capacity_kg=data.capacity_kg,
            volume_cbm=data.volume_cbm,
            is_available=data.is_available,
            rc_number=data.rc_number,
            insurance_expiry=data.insurance_expiry,
            fitness_expiry=data.fitness_expiry,
            telematics_device_id=data.telematics_device_id,
            created_at=now,
            updated_at=now,
        )
        session.add(vehicle)

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE",
            entity_name="Vehicle",
            entity_id=vehicle_id,
            changes={"license_plate": clean_plate, "vehicle_type": data.vehicle_type, "capacity_kg": data.capacity_kg},
        )
        session.add(audit)

        await session.commit()

        # Check document expiry status
        has_expired = False
        if data.insurance_expiry and data.insurance_expiry < now:
            has_expired = True
        if data.fitness_expiry and data.fitness_expiry < now:
            has_expired = True

        v_status = "EXPIRED_DOCUMENTS" if has_expired else "ACTIVE" if data.is_available else "MAINTENANCE"

        return VehicleListItem(
            id=str(vehicle.id),
            transporter_id=str(t.id),
            transporter_name=t.name,
            license_plate=vehicle.license_plate,
            vehicle_type=vehicle.vehicle_type,
            capacity_kg=float(vehicle.capacity_kg),
            volume_cbm=float(vehicle.volume_cbm) if vehicle.volume_cbm else None,
            is_available=vehicle.is_available,
            status=v_status,
            has_expired_documents=has_expired,
            insurance_expiry=vehicle.insurance_expiry,
            fitness_expiry=vehicle.fitness_expiry,
            rc_number=vehicle.rc_number,
            telematics_device_id=vehicle.telematics_device_id,
            assigned_driver_id=None,
            assigned_driver_name=None,
            created_at=vehicle.created_at,
        )

    @staticmethod
    async def list_vehicles(
        session: AsyncSession,
        organization_id: uuid.UUID,
        transporter_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        is_available: Optional[bool] = None,
        has_expired_docs: Optional[bool] = None,
    ) -> PaginatedVehiclesResponse:
        """
        Lists fleet vehicles across transporters with dynamic document expiration checks.
        """
        filters = [
            Vehicle.organization_id == organization_id,
            Vehicle.is_deleted.is_(False),
        ]

        if transporter_id:
            filters.append(Vehicle.transporter_id == transporter_id)

        if is_available is not None:
            filters.append(Vehicle.is_available.is_(is_available))

        if vehicle_type and vehicle_type.upper() != "ALL":
            filters.append(Vehicle.vehicle_type == vehicle_type)

        now = datetime.now(timezone.utc)
        if has_expired_docs is True:
            filters.append(
                or_(
                    and_(Vehicle.insurance_expiry.is_not(None), Vehicle.insurance_expiry < now),
                    and_(Vehicle.fitness_expiry.is_not(None), Vehicle.fitness_expiry < now),
                )
            )
        elif has_expired_docs is False:
            filters.append(
                and_(
                    or_(Vehicle.insurance_expiry.is_(None), Vehicle.insurance_expiry >= now),
                    or_(Vehicle.fitness_expiry.is_(None), Vehicle.fitness_expiry >= now),
                )
            )

        if search:
            s = f"%{search.strip()}%"
            filters.append(
                or_(
                    Vehicle.license_plate.ilike(s),
                    Vehicle.vehicle_type.ilike(s),
                    Vehicle.rc_number.ilike(s),
                    Vehicle.telematics_device_id.ilike(s),
                    Transporter.name.ilike(s),
                )
            )

        count_stmt = (
            select(func.count(Vehicle.id))
            .join(Transporter, Vehicle.transporter_id == Transporter.id)
            .where(and_(*filters))
        )
        total = (await session.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        offset = (page - 1) * page_size

        stmt = (
            select(Vehicle, Transporter)
            .join(Transporter, Vehicle.transporter_id == Transporter.id)
            .where(and_(*filters))
            .order_by(desc(Vehicle.created_at))
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).all()

        items = []
        for v, t in rows:
            has_expired = False
            if v.insurance_expiry and v.insurance_expiry < now:
                has_expired = True
            if v.fitness_expiry and v.fitness_expiry < now:
                has_expired = True

            v_status = "EXPIRED_DOCUMENTS" if has_expired else "ACTIVE" if v.is_available else "MAINTENANCE"

            # Check driver mapping from transporter compliance details
            meta = t.compliance_details or {}
            driver_mappings = meta.get("assigned_vehicle_mappings", {})
            assigned_d_name = None
            assigned_d_id = None
            for d_id_str, v_id_str in driver_mappings.items():
                if v_id_str == str(v.id):
                    assigned_d_id = d_id_str
                    break

            items.append(
                VehicleListItem(
                    id=str(v.id),
                    transporter_id=str(t.id),
                    transporter_name=t.name,
                    license_plate=v.license_plate,
                    vehicle_type=v.vehicle_type,
                    capacity_kg=float(v.capacity_kg),
                    volume_cbm=float(v.volume_cbm) if v.volume_cbm else None,
                    is_available=v.is_available,
                    status=v_status,
                    has_expired_documents=has_expired,
                    insurance_expiry=v.insurance_expiry,
                    fitness_expiry=v.fitness_expiry,
                    rc_number=v.rc_number,
                    telematics_device_id=v.telematics_device_id,
                    assigned_driver_id=assigned_d_id,
                    assigned_driver_name=assigned_d_name,
                    created_at=v.created_at,
                )
            )

        return PaginatedVehiclesResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def update_vehicle(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        data: VehicleUpdateRequest,
    ) -> VehicleListItem:
        """
        Updates vehicle details and logs audit entry.
        """
        stmt = (
            select(Vehicle, Transporter)
            .join(Transporter, Vehicle.transporter_id == Transporter.id)
            .where(
                and_(
                    Vehicle.id == vehicle_id,
                    Vehicle.organization_id == organization_id,
                    Vehicle.is_deleted.is_(False),
                )
            )
        )
        row = (await session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")

        v, t = row
        old_vals = {}
        new_vals = {}

        fields = [
            "vehicle_type", "capacity_kg", "volume_cbm", "rc_number",
            "insurance_expiry", "fitness_expiry", "telematics_device_id", "is_available"
        ]
        update_dict = data.model_dump(exclude_unset=True)

        for f in fields:
            if f in update_dict:
                val = getattr(data, f)
                old_val = getattr(v, f)
                if old_val != val:
                    old_vals[f] = _json_safe(old_val)
                    new_vals[f] = _json_safe(val)
                    setattr(v, f, val)

        v.updated_at = datetime.now(timezone.utc)

        if new_vals:
            audit = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                user_id=user_id,
                action="UPDATE",
                entity_name="Vehicle",
                entity_id=vehicle_id,
                changes={"old": old_vals, "new": new_vals},
            )
            session.add(audit)

        await session.commit()

        now = datetime.now(timezone.utc)
        has_expired = False
        if v.insurance_expiry and v.insurance_expiry < now:
            has_expired = True
        if v.fitness_expiry and v.fitness_expiry < now:
            has_expired = True

        v_status = "EXPIRED_DOCUMENTS" if has_expired else "ACTIVE" if v.is_available else "MAINTENANCE"

        return VehicleListItem(
            id=str(v.id),
            transporter_id=str(t.id),
            transporter_name=t.name,
            license_plate=v.license_plate,
            vehicle_type=v.vehicle_type,
            capacity_kg=float(v.capacity_kg),
            volume_cbm=float(v.volume_cbm) if v.volume_cbm else None,
            is_available=v.is_available,
            status=v_status,
            has_expired_documents=has_expired,
            insurance_expiry=v.insurance_expiry,
            fitness_expiry=v.fitness_expiry,
            rc_number=v.rc_number,
            telematics_device_id=v.telematics_device_id,
            assigned_driver_id=None,
            assigned_driver_name=None,
            created_at=v.created_at,
        )

    @staticmethod
    async def delete_vehicle(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        vehicle_id: uuid.UUID,
    ) -> Dict[str, str]:
        """
        Soft deletes a vehicle record from the active fleet.
        """
        stmt = select(Vehicle).where(
            and_(
                Vehicle.id == vehicle_id,
                Vehicle.organization_id == organization_id,
                Vehicle.is_deleted.is_(False),
            )
        )
        v = (await session.execute(stmt)).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")

        now = datetime.now(timezone.utc)
        v.is_deleted = True
        v.deleted_at = now
        v.is_available = False

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="DELETE",
            entity_name="Vehicle",
            entity_id=vehicle_id,
            changes={"license_plate": v.license_plate, "deleted": True},
        )
        session.add(audit)
        await session.commit()
        return {"status": "success", "message": f"Vehicle {v.license_plate} deleted successfully."}

    # =========================================================================
    # DRIVER METHODS
    # =========================================================================

    @staticmethod
    async def create_driver(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: DriverCreateRequest,
    ) -> DriverListItem:
        """
        Registers a new commercial driver under a carrier.
        Enforces unique driver phone within the organization.
        """
        t = await session.get(Transporter, data.transporter_id)
        if not t or t.organization_id != organization_id or t.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        clean_phone = data.phone.strip()
        existing_phone_stmt = select(Driver).where(
            and_(
                Driver.organization_id == organization_id,
                Driver.phone == clean_phone,
                Driver.is_deleted.is_(False),
            )
        )
        if (await session.execute(existing_phone_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Driver with phone number '{clean_phone}' already exists in your organization.",
            )

        driver_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        driver = Driver(
            id=driver_id,
            organization_id=organization_id,
            transporter_id=data.transporter_id,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            phone=clean_phone,
            license_number=data.license_number.strip().upper(),
            license_expiry=data.license_expiry,
            is_available=data.is_available,
            created_at=now,
            updated_at=now,
        )
        session.add(driver)

        # Handle vehicle assignment if provided
        assigned_plate = None
        if data.assigned_vehicle_id:
            vehicle = await session.get(Vehicle, data.assigned_vehicle_id)
            if not vehicle or vehicle.transporter_id != data.transporter_id or vehicle.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned vehicle does not belong to this transporter.",
                )
            assigned_plate = vehicle.license_plate

            meta = dict(t.compliance_details or {})
            mappings = dict(meta.get("assigned_vehicle_mappings", {}))
            mappings[str(driver_id)] = str(data.assigned_vehicle_id)
            meta["assigned_vehicle_mappings"] = mappings
            t.compliance_details = meta

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE",
            entity_name="Driver",
            entity_id=driver_id,
            changes={
                "name": f"{driver.first_name} {driver.last_name}",
                "phone": clean_phone,
                "license_number": _mask_license(driver.license_number),
            },
        )
        session.add(audit)

        await session.commit()

        is_lic_expired = bool(data.license_expiry and data.license_expiry < now)
        d_status = "EXPIRED_LICENSE" if is_lic_expired else "ACTIVE" if data.is_available else "OFF_DUTY"

        return DriverListItem(
            id=str(driver.id),
            transporter_id=str(t.id),
            transporter_name=t.name,
            first_name=driver.first_name,
            last_name=driver.last_name,
            full_name=f"{driver.first_name} {driver.last_name}",
            phone=driver.phone,
            license_number=driver.license_number,
            license_number_masked=_mask_license(driver.license_number),
            license_expiry=driver.license_expiry,
            is_license_expired=is_lic_expired,
            is_available=driver.is_available,
            status=d_status,
            assigned_vehicle_id=str(data.assigned_vehicle_id) if data.assigned_vehicle_id else None,
            assigned_vehicle_plate=assigned_plate,
            created_at=driver.created_at,
        )

    @staticmethod
    async def list_drivers(
        session: AsyncSession,
        organization_id: uuid.UUID,
        transporter_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        is_available: Optional[bool] = None,
    ) -> PaginatedDriversResponse:
        """
        Lists commercial drivers with masked license privacy and validity checks.
        """
        filters = [
            Driver.organization_id == organization_id,
            Driver.is_deleted.is_(False),
        ]

        if transporter_id:
            filters.append(Driver.transporter_id == transporter_id)

        if is_available is not None:
            filters.append(Driver.is_available.is_(is_available))

        if search:
            s = f"%{search.strip()}%"
            filters.append(
                or_(
                    Driver.first_name.ilike(s),
                    Driver.last_name.ilike(s),
                    Driver.phone.ilike(s),
                    Driver.license_number.ilike(s),
                    Transporter.name.ilike(s),
                )
            )

        count_stmt = (
            select(func.count(Driver.id))
            .join(Transporter, Driver.transporter_id == Transporter.id)
            .where(and_(*filters))
        )
        total = (await session.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        offset = (page - 1) * page_size

        stmt = (
            select(Driver, Transporter)
            .join(Transporter, Driver.transporter_id == Transporter.id)
            .where(and_(*filters))
            .order_by(desc(Driver.created_at))
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).all()

        now = datetime.now(timezone.utc)
        items = []
        for d, t in rows:
            is_lic_expired = bool(d.license_expiry and d.license_expiry < now)
            d_status = "EXPIRED_LICENSE" if is_lic_expired else "ACTIVE" if d.is_available else "OFF_DUTY"

            meta = t.compliance_details or {}
            driver_mappings = meta.get("assigned_vehicle_mappings", {})
            assigned_v_id = driver_mappings.get(str(d.id))
            assigned_plate = None

            if assigned_v_id:
                # Query license plate
                v_obj = await session.get(Vehicle, uuid.UUID(assigned_v_id))
                if v_obj and not v_obj.is_deleted:
                    assigned_plate = v_obj.license_plate

            items.append(
                DriverListItem(
                    id=str(d.id),
                    transporter_id=str(t.id),
                    transporter_name=t.name,
                    first_name=d.first_name,
                    last_name=d.last_name,
                    full_name=f"{d.first_name} {d.last_name}",
                    phone=d.phone,
                    license_number=d.license_number,
                    license_number_masked=_mask_license(d.license_number),
                    license_expiry=d.license_expiry,
                    is_license_expired=is_lic_expired,
                    is_available=d.is_available,
                    status=d_status,
                    assigned_vehicle_id=assigned_v_id,
                    assigned_vehicle_plate=assigned_plate,
                    created_at=d.created_at,
                )
            )

        return PaginatedDriversResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def update_driver(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        driver_id: uuid.UUID,
        data: DriverUpdateRequest,
    ) -> DriverListItem:
        """
        Updates driver profile, license dates, and assigned vehicle.
        """
        stmt = (
            select(Driver, Transporter)
            .join(Transporter, Driver.transporter_id == Transporter.id)
            .where(
                and_(
                    Driver.id == driver_id,
                    Driver.organization_id == organization_id,
                    Driver.is_deleted.is_(False),
                )
            )
        )
        row = (await session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found.")

        d, t = row
        old_vals = {}
        new_vals = {}

        fields = ["first_name", "last_name", "phone", "license_number", "license_expiry", "is_available"]
        update_dict = data.model_dump(exclude_unset=True)

        for f in fields:
            if f in update_dict:
                val = getattr(data, f)
                old_val = getattr(d, f)
                if old_val != val:
                    old_vals[f] = _json_safe(old_val)
                    new_vals[f] = _json_safe(val)
                    setattr(d, f, val)

        # Vehicle assignment update
        assigned_plate = None
        if "assigned_vehicle_id" in update_dict:
            meta = dict(t.compliance_details or {})
            mappings = dict(meta.get("assigned_vehicle_mappings", {}))
            if data.assigned_vehicle_id:
                v = await session.get(Vehicle, data.assigned_vehicle_id)
                if not v or v.transporter_id != d.transporter_id or v.is_deleted:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned vehicle is invalid.")
                mappings[str(d.id)] = str(data.assigned_vehicle_id)
                assigned_plate = v.license_plate
            else:
                mappings.pop(str(d.id), None)
            meta["assigned_vehicle_mappings"] = mappings
            t.compliance_details = meta

        d.updated_at = datetime.now(timezone.utc)

        if new_vals:
            audit = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                user_id=user_id,
                action="UPDATE",
                entity_name="Driver",
                entity_id=driver_id,
                changes={"old": old_vals, "new": new_vals},
            )
            session.add(audit)

        await session.commit()

        now = datetime.now(timezone.utc)
        is_lic_expired = bool(d.license_expiry and d.license_expiry < now)
        d_status = "EXPIRED_LICENSE" if is_lic_expired else "ACTIVE" if d.is_available else "OFF_DUTY"

        meta = t.compliance_details or {}
        driver_mappings = meta.get("assigned_vehicle_mappings", {})
        assigned_v_id = driver_mappings.get(str(d.id))

        return DriverListItem(
            id=str(d.id),
            transporter_id=str(t.id),
            transporter_name=t.name,
            first_name=d.first_name,
            last_name=d.last_name,
            full_name=f"{d.first_name} {d.last_name}",
            phone=d.phone,
            license_number=d.license_number,
            license_number_masked=_mask_license(d.license_number),
            license_expiry=d.license_expiry,
            is_license_expired=is_lic_expired,
            is_available=d.is_available,
            status=d_status,
            assigned_vehicle_id=assigned_v_id,
            assigned_vehicle_plate=assigned_plate,
            created_at=d.created_at,
        )

    @staticmethod
    async def assign_driver_to_vehicle(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        driver_id: uuid.UUID,
        data: DriverAssignmentRequest,
    ) -> DriverListItem:
        """
        Assigns or unassigns a driver to a specific commercial vehicle.
        Blocks assignment if driver license has expired.
        """
        stmt = (
            select(Driver, Transporter)
            .join(Transporter, Driver.transporter_id == Transporter.id)
            .where(
                and_(
                    Driver.id == driver_id,
                    Driver.organization_id == organization_id,
                    Driver.is_deleted.is_(False),
                )
            )
        )
        row = (await session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found.")

        d, t = row
        now = datetime.now(timezone.utc)

        # Business Rule: Expired driver license cannot be assigned to vehicle
        if data.vehicle_id and d.license_expiry and d.license_expiry < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign driver to vehicle: Driver's commercial license has expired.",
            )

        meta = dict(t.compliance_details or {})
        mappings = dict(meta.get("assigned_vehicle_mappings", {}))
        assigned_plate = None

        if data.vehicle_id:
            v = await session.get(Vehicle, data.vehicle_id)
            if not v or v.transporter_id != d.transporter_id or v.is_deleted:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected vehicle is invalid.")
            mappings[str(d.id)] = str(data.vehicle_id)
            assigned_plate = v.license_plate
        else:
            mappings.pop(str(d.id), None)

        meta["assigned_vehicle_mappings"] = mappings
        t.compliance_details = meta

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="ASSIGN_VEHICLE",
            entity_name="Driver",
            entity_id=driver_id,
            changes={"vehicle_id": str(data.vehicle_id) if data.vehicle_id else None},
        )
        session.add(audit)
        await session.commit()

        is_lic_expired = bool(d.license_expiry and d.license_expiry < now)
        d_status = "EXPIRED_LICENSE" if is_lic_expired else "ACTIVE" if d.is_available else "OFF_DUTY"

        return DriverListItem(
            id=str(d.id),
            transporter_id=str(t.id),
            transporter_name=t.name,
            first_name=d.first_name,
            last_name=d.last_name,
            full_name=f"{d.first_name} {d.last_name}",
            phone=d.phone,
            license_number=d.license_number,
            license_number_masked=_mask_license(d.license_number),
            license_expiry=d.license_expiry,
            is_license_expired=is_lic_expired,
            is_available=d.is_available,
            status=d_status,
            assigned_vehicle_id=str(data.vehicle_id) if data.vehicle_id else None,
            assigned_vehicle_plate=assigned_plate,
            created_at=d.created_at,
        )

    @staticmethod
    async def delete_driver(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        driver_id: uuid.UUID,
    ) -> Dict[str, str]:
        """
        Soft deletes a driver.
        """
        stmt = select(Driver).where(
            and_(
                Driver.id == driver_id,
                Driver.organization_id == organization_id,
                Driver.is_deleted.is_(False),
            )
        )
        d = (await session.execute(stmt)).scalar_one_or_none()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found.")

        now = datetime.now(timezone.utc)
        d.is_deleted = True
        d.deleted_at = now
        d.is_available = False

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="DELETE",
            entity_name="Driver",
            entity_id=driver_id,
            changes={"name": f"{d.first_name} {d.last_name}", "deleted": True},
        )
        session.add(audit)
        await session.commit()
        return {"status": "success", "message": f"Driver {d.first_name} {d.last_name} deleted successfully."}

    # =========================================================================
    # SERVICE AREA METHODS
    # =========================================================================

    @staticmethod
    async def add_service_area(
        session: AsyncSession,
        organization_id: uuid.UUID,
        transporter_id: uuid.UUID,
        data: ServiceAreaCreateRequest,
    ) -> ServiceAreaResponse:
        t = await session.get(Transporter, transporter_id)
        if not t or t.organization_id != organization_id or t.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transporter not found.")

        sa_id = uuid.uuid4()
        sa = TransporterServiceArea(
            id=sa_id,
            transporter_id=transporter_id,
            origin_region=data.origin_region.strip(),
            destination_region=data.destination_region.strip(),
            origin_postal_code_prefix=data.origin_postal_code_prefix,
            destination_postal_code_prefix=data.destination_postal_code_prefix,
            estimated_transit_hours=data.estimated_transit_hours,
            is_active=True,
        )
        session.add(sa)
        await session.commit()

        return ServiceAreaResponse(
            id=str(sa.id),
            transporter_id=str(sa.transporter_id),
            origin_region=sa.origin_region,
            destination_region=sa.destination_region,
            origin_postal_code_prefix=sa.origin_postal_code_prefix,
            destination_postal_code_prefix=sa.destination_postal_code_prefix,
            estimated_transit_hours=sa.estimated_transit_hours,
            is_active=sa.is_active,
            created_at=sa.created_at,
        )

    # =========================================================================
    # BUSINESS RULE VERIFIERS
    # =========================================================================

    @staticmethod
    def verify_transporter_eligible_for_booking(transporter: Transporter) -> None:
        """
        Business Rule: Unverified or suspended transporters cannot receive active bookings.
        """
        meta = transporter.compliance_details or {}
        v_status = meta.get("verification_status", TransporterVerificationStatus.REGISTERED)

        if not transporter.is_active or v_status == TransporterVerificationStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transporter '{transporter.name}' is suspended and cannot accept bookings or assignments.",
            )

        if v_status != TransporterVerificationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transporter '{transporter.name}' is unverified ({v_status}). Only verified transporters can receive active bookings.",
            )

    @staticmethod
    def verify_vehicle_capacity_and_documents(vehicle: Vehicle, required_weight_kg: float) -> None:
        """
        Business Rules:
        1. Vehicle capacity must satisfy shipment requirements.
        2. Expired mandatory documents (insurance or fitness) trigger eligibility restrictions.
        """
        if float(vehicle.capacity_kg) < required_weight_kg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle capacity ({vehicle.capacity_kg} kg) is insufficient for shipment weight ({required_weight_kg} kg).",
            )

        now = datetime.now(timezone.utc)
        if vehicle.insurance_expiry and vehicle.insurance_expiry < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{vehicle.license_plate}' cannot be dispatched: Insurance policy has expired.",
            )

        if vehicle.fitness_expiry and vehicle.fitness_expiry < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{vehicle.license_plate}' cannot be dispatched: Fitness / inspection certificate has expired.",
            )
