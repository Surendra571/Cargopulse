"""
CargoPulse Development Seed Data Script
Generates a realistic set of manufacturers, carriers, vehicles, drivers,
shipments, bookings, pickup commitments, exceptions, events, and e-PODs.

Usage:
    python -m app.scripts.seed_dashboard_data
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.auth import Organization, User, Role, UserRole, Permission, RolePermission
from app.models.enums import (
    AssignmentStatus,
    BookingStatus,
    CommitmentStatus,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    OrganizationType,
    PODVerificationStatus,
    ShipmentStatus,
    UserRoleType,
)
from app.models.operations import ExceptionRecord, ProofOfDelivery
from app.models.shipment import (
    PickupCommitment,
    Shipment,
    ShipmentAssignment,
    ShipmentEvent,
    TransporterBooking,
)
from app.models.transporter import (
    Driver,
    OrganizationTransporter,
    Transporter,
    Vehicle,
)


async def seed_data():
    now = datetime.now(timezone.utc)
    print("🌱 Starting CargoPulse Operations Dashboard seed...")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Ensure or create Indian Manufacturer organization
            org_stmt = select(Organization).where(Organization.slug == "kaveri-precision-mfg")
            org = (await session.execute(org_stmt)).scalar_one_or_none()

            if not org:
                org = Organization(
                    id=uuid.uuid4(),
                    name="Kaveri Precision Mfg — Bengaluru",
                    slug="kaveri-precision-mfg",
                    org_type=OrganizationType.MANUFACTURER,
                    billing_email="dispatch@kaverimfg.in",
                    is_active=True,
                    settings={"tier": "enterprise", "timezone": "Asia/Kolkata", "currency": "INR"},
                )
                session.add(org)
                await session.flush()
                print(f"Created organization: {org.name} ({org.id})")
            else:
                print(f"Found existing demo organization: {org.name} ({org.id})")

            from app.services.organization_service import OrganizationService
            await OrganizationService.ensure_standard_roles_and_permissions(session, org.id)

            # Ensure admin user & role (and refresh demo password if user already exists)
            user_stmt = select(User).where(User.email == "ananya.rao@kaverimfg.in")
            user = (await session.execute(user_stmt)).scalar_one_or_none()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    email="ananya.rao@kaverimfg.in",
                    hashed_password=hash_password("Password123!"),
                    first_name="Ananya",
                    last_name="Rao",
                    phone="+91 98450 41290",
                    is_active=True,
                    is_superadmin=False,
                )
                session.add(user)
                await session.flush()
                print(f"Created demo ops user: {user.email}")
            else:
                user.hashed_password = hash_password("Password123!")
                user.is_active = True
                user.first_name = "Ananya"
                user.last_name = "Rao"
                user.phone = "+91 98450 41290"
                print(f"Updated demo ops user credentials: {user.email}")

            role_stmt = select(Role).where(
                Role.organization_id == org.id,
                Role.role_type == UserRoleType.ORGANIZATION_ADMIN,
            )
            admin_role = (await session.execute(role_stmt)).scalar_one_or_none()
            if admin_role:
                ur_stmt = select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == admin_role.id,
                )
                if not (await session.execute(ur_stmt)).scalar_one_or_none():
                    session.add(UserRole(user_id=user.id, role_id=admin_role.id))

            # 2. Seed 4 Indian Transporters with distinct profiles
            carrier_data = [
                {
                    "name": "Deccan Freightlines",
                    "code": "DCCN",
                    "email": "dispatch@deccanfreight.in",
                    "phone": "+91 80 4123 8901",
                    "reliability": 99.2,
                    "total_deliv": 142,
                    "ontime_deliv": 140,
                    "vehicles": [
                        ("KA-01-MN-4829", "32ft Multi-Axle Closed", "KA-01-MN-4829"),
                        ("KA-01-MN-4830", "20ft Container", "KA-01-MN-4830"),
                    ],
                    "drivers": [
                        ("Rajesh Kulkarni", "DL-KA01-20180045123", "+91 98451 10293"),
                        ("Suresh Nair", "DL-KA01-20190088124", "+91 98451 10294"),
                    ],
                },
                {
                    "name": "Sahyadri Roadways",
                    "code": "SHYD",
                    "email": "ops@sahyadriroadways.in",
                    "phone": "+91 20 6712 4402",
                    "reliability": 97.8,
                    "total_deliv": 230,
                    "ontime_deliv": 224,
                    "vehicles": [
                        ("MH-12-TR-8821", "32ft SXL Container", "MH-12-TR-8821"),
                        ("MH-12-TR-8822", "24ft Open Flatbed", "MH-12-TR-8822"),
                    ],
                    "drivers": [
                        ("Vikram Deshmukh", "DL-MH12-20170044910", "+91 98220 44910"),
                        ("Amit Patil", "DL-MH12-20200088129", "+91 98220 44911"),
                    ],
                },
                {
                    "name": "Vindhya Logistics",
                    "code": "VNDH",
                    "email": "operations@vindhyalogistics.in",
                    "phone": "+91 44 2815 3303",
                    "reliability": 95.4,
                    "total_deliv": 320,
                    "ontime_deliv": 305,
                    "vehicles": [
                        ("TN-09-CG-3342", "32ft Reefer Container", "TN-09-CG-3342"),
                        ("TN-09-CG-3343", "32ft MXL Closed", "TN-09-CG-3343"),
                    ],
                    "drivers": [
                        ("Karthik Subramanian", "DL-TN09-20160031092", "+91 98401 31092"),
                        ("Murugan Selvam", "DL-TN09-20190055019", "+91 98401 31093"),
                    ],
                },
                {
                    "name": "Bharati Heavy Haul",
                    "code": "BHRT",
                    "email": "dispatch@bharatiheavy.in",
                    "phone": "+91 40 2331 1104",
                    "reliability": 88.1,
                    "total_deliv": 64,
                    "ontime_deliv": 56,
                    "vehicles": [
                        ("TS-07-HF-1104", "40ft Low-Bed Trailer", "TS-07-HF-1104"),
                    ],
                    "drivers": [
                        ("Ramesh Reddy", "DL-TS07-20180011094", "+91 98490 11094"),
                    ],
                },
            ]

            created_carriers = []
            for c_info in carrier_data:
                c_stmt = select(Transporter).where(
                    Transporter.organization_id == org.id,
                    Transporter.code == c_info["code"],
                )
                carrier = (await session.execute(c_stmt)).scalar_one_or_none()
                if not carrier:
                    carrier = Transporter(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        name=c_info["name"],
                        code=c_info["code"],
                        email=c_info["email"],
                        phone=c_info["phone"],
                        reliability_score=c_info["reliability"],
                        total_deliveries=c_info["total_deliv"],
                        on_time_deliveries=c_info["ontime_deliv"],
                        is_active=True,
                    )
                    session.add(carrier)
                    await session.flush()

                    # Add OrganizationTransporter link
                    org_transporter = OrganizationTransporter(
                        organization_id=org.id,
                        transporter_id=carrier.id,
                        status="ACTIVE",
                        contract_reference=f"MSA-{carrier.code}-2026",
                    )
                    session.add(org_transporter)

                    # Add Vehicles
                    vehicles = []
                    for v_num, v_type, v_plate in c_info["vehicles"]:
                        veh = Vehicle(
                            id=uuid.uuid4(),
                            organization_id=org.id,
                            transporter_id=carrier.id,
                            vehicle_type=v_type,
                            license_plate=v_plate,
                            capacity_kg=22000.0,
                            is_available=True,
                        )
                        session.add(veh)
                        vehicles.append(veh)

                    # Add Drivers
                    drivers = []
                    for d_name, d_cdl, d_phone in c_info["drivers"]:
                        parts = d_name.split()
                        first = parts[0]
                        last = parts[1] if len(parts) > 1 else "Driver"
                        drv = Driver(
                            id=uuid.uuid4(),
                            organization_id=org.id,
                            transporter_id=carrier.id,
                            first_name=first,
                            last_name=last,
                            license_number=d_cdl,
                            phone=d_phone,
                            is_available=True,
                        )
                        session.add(drv)
                        drivers.append(drv)

                    await session.flush()
                    print(f"Created carrier: {carrier.name} with vehicles and drivers.")

                created_carriers.append(carrier)

            # 3. Seed 25 realistic Indian B2B shipments with associated records
            shipment_templates = [
                # Delivered (10)
                ("SHP-2026-000101", "Bengaluru, KA", "Chennai, TN", ShipmentStatus.DELIVERED, -5, -4, -4, -2, -2, 0),
                ("SHP-2026-000102", "Pune, MH", "Hyderabad, TG", ShipmentStatus.DELIVERED, -4, -3, -3, -2, -2, 1),
                ("SHP-2026-000103", "Chennai, TN", "Coimbatore, TN", ShipmentStatus.DELIVERED, -6, -5, -5, -3, -3, 2),
                ("SHP-2026-000104", "Ahmedabad, GJ", "Mumbai, MH", ShipmentStatus.DELIVERED, -5, -4, -4, -3, -3, 0),
                ("SHP-2026-000105", "Bengaluru, KA", "Hyderabad, TG", ShipmentStatus.DELIVERED, -3, -2, -2, -1, -1, 1),
                ("SHP-2026-000106", "Pune, MH", "Ahmedabad, GJ", ShipmentStatus.DELIVERED, -4, -3, -3, -2, -2, 2),
                ("SHP-2026-000107", "Gurugram, HR", "Jaipur, RJ", ShipmentStatus.DELIVERED, -7, -6, -6, -4, -4, 0),
                ("SHP-2026-000108", "Hyderabad, TG", "Nagpur, MH", ShipmentStatus.DELIVERED, -5, -4, -4, -3, -3, 1),
                ("SHP-2026-000109", "Bengaluru, KA", "Mumbai, MH", ShipmentStatus.DELIVERED, -8, -7, -7, -4, -4, 2),
                ("SHP-2026-000110", "Chennai, TN", "Pune, MH", ShipmentStatus.DELIVERED, -2, -1, -1, 0, 0, 0),

                # In-Transit (6)
                ("SHP-2026-000111", "Bengaluru, KA", "Chennai, TN", ShipmentStatus.IN_TRANSIT, -1, -1, -1, 1, None, 0),
                ("SHP-2026-000112", "Pune, MH", "Hyderabad, TG", ShipmentStatus.IN_TRANSIT, -1, -1, -1, 2, None, 1),
                ("SHP-2026-000113", "Chennai, TN", "Bengaluru, KA", ShipmentStatus.IN_TRANSIT, -2, -2, -2, 1, None, 2),
                ("SHP-2026-000114", "Ahmedabad, GJ", "Pune, MH", ShipmentStatus.IN_TRANSIT, -1, -1, -1, 1, None, 0),
                ("SHP-2026-000115", "Gurugram, HR", "Ahmedabad, GJ", ShipmentStatus.OUT_FOR_DELIVERY, -1, -1, -1, 0, None, 1),
                ("SHP-2026-000116", "Bengaluru, KA", "Mumbai, MH", ShipmentStatus.IN_TRANSIT, -2, -2, -2, -1, None, 3),

                # Committed / Dispatched / At Pickup (4)
                ("SHP-2026-000125", "Bengaluru, KA", "Chennai, TN", ShipmentStatus.COMMITTED, 0, 0, None, 2, None, 0),
                ("SHP-2026-000126", "Pune, MH", "Mumbai, MH", ShipmentStatus.DISPATCHED, 0, 0, None, 2, None, 1),
                ("SHP-2026-000127", "Chennai, TN", "Hyderabad, TG", ShipmentStatus.AT_PICKUP, -1, 0, None, 1, None, 2),
                ("SHP-2026-000128", "Ahmedabad, GJ", "Surat, GJ", ShipmentStatus.COMMITTED, 0, 1, None, 3, None, 0),

                # Draft / Pending Acceptance (2)
                ("SHP-2026-000131", "Bengaluru, KA", "Pune, MH", ShipmentStatus.PENDING_ACCEPTANCE, 0, 2, None, 4, None, 1),
                ("SHP-2026-000132", "Gurugram, HR", "Lucknow, UP", ShipmentStatus.DRAFT, 0, 3, None, 5, None, 2),

                # Exceptions / Failed Pickups (3)
                ("SHP-2026-000118", "Bengaluru, KA", "Mumbai, MH", ShipmentStatus.EXCEPTION, -1, -1, None, 1, None, 3),
                ("SHP-2026-000119", "Pune, MH", "Hyderabad, TG", ShipmentStatus.EXCEPTION, -1, -1, -1, 1, None, 1),
                ("SHP-2026-000129", "Bengaluru, KA", "Hyderabad, TG", ShipmentStatus.EXCEPTION, -2, -2, None, 0, None, 3),
            ]

            seeded_count = 0
            for (
                trk_num,
                orig,
                dest,
                st,
                created_offset_days,
                sched_pk_offset_days,
                actual_pk_offset_days,
                sched_deliv_offset_days,
                actual_deliv_offset_days,
                carrier_idx,
            ) in shipment_templates:
                # Check if exists
                s_check = select(Shipment).where(
                    Shipment.organization_id == org.id,
                    Shipment.tracking_number == trk_num,
                )
                existing_s = (await session.execute(s_check)).scalar_one_or_none()
                if existing_s:
                    continue

                carrier = created_carriers[carrier_idx % len(created_carriers)]

                # Parse cities
                orig_city, orig_state = [x.strip() for x in orig.split(",")]
                dest_city, dest_state = [x.strip() for x in dest.split(",")]

                created_dt = now + timedelta(days=created_offset_days, hours=2)
                sched_pk_dt = now + timedelta(days=sched_pk_offset_days, hours=10)
                actual_pk_dt = (
                    now + timedelta(days=actual_pk_offset_days, hours=10, minutes=20)
                    if actual_pk_offset_days is not None
                    else None
                )
                sched_deliv_dt = now + timedelta(days=sched_deliv_offset_days, hours=16)
                actual_deliv_dt = (
                    now + timedelta(days=actual_deliv_offset_days, hours=15, minutes=45)
                    if actual_deliv_offset_days is not None
                    else None
                )

                shipment = Shipment(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    tracking_number=trk_num,
                    status=st,
                    origin_name=f"{orig_city} Plant — Peenya Industrial Area",
                    origin_address=f"Plot 42, Industrial Estate, {orig_city}, {orig_state}",
                    origin_city=orig_city,
                    origin_state=orig_state,
                    origin_postal_code="560058",
                    origin_contact_name="Plant Dispatch Lead",
                    origin_contact_phone="+91 80 4112 0001",
                    destination_name=f"{dest_city} Distribution Hub",
                    destination_address=f"Sector 14, Logistics Park, {dest_city}, {dest_state}",
                    destination_city=dest_city,
                    destination_state=dest_state,
                    destination_postal_code="600058",
                    destination_contact_name="Godrej Industrial Systems",
                    destination_contact_phone="+91 44 2625 0002",
                    scheduled_pickup_time=sched_pk_dt,
                    actual_pickup_time=actual_pk_dt,
                    expected_delivery_time=sched_deliv_dt,
                    actual_delivery_time=actual_deliv_dt,
                    total_weight_kg=16800.0,
                    package_count=24,
                    goods_description="Precision CNC assemblies and industrial switchgear",
                    is_hazardous=False,
                )
                session.add(shipment)
                await session.flush()

                # Add Transporter Booking
                booking_status = (
                    BookingStatus.ACCEPTED
                    if st != ShipmentStatus.DRAFT
                    else BookingStatus.REQUESTED
                )
                booking = TransporterBooking(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    shipment_id=shipment.id,
                    transporter_id=carrier.id,
                    status=booking_status,
                    agreed_rate=42500.0,
                    expires_at=sched_pk_dt,
                )
                session.add(booking)

                # Add Pickup Commitment
                is_breached = trk_num in ["SHP-2026-000118", "SHP-2026-000129"]
                commitment_status = (
                    CommitmentStatus.BREACHED
                    if is_breached
                    else (
                        CommitmentStatus.CONFIRMED
                        if actual_pk_dt
                        else CommitmentStatus.PENDING
                    )
                )
                commitment = PickupCommitment(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    shipment_id=shipment.id,
                    transporter_id=carrier.id,
                    committed_pickup_slot_start=sched_pk_dt,
                    committed_pickup_slot_end=sched_pk_dt + timedelta(hours=2),
                    status=commitment_status,
                    actual_arrival_at=actual_pk_dt,
                    is_breached=is_breached,
                    breach_reason="Carrier vehicle no-show" if is_breached else None,
                )
                session.add(commitment)

                # Add Shipment Events
                ev_created = ShipmentEvent(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    shipment_id=shipment.id,
                    event_type="SHIPMENT_CREATED",
                    description=f"Shipment {trk_num} created by manufacturer.",
                    occurred_at=created_dt,
                    location_name=f"{orig_city}, {orig_state}",
                    source="SYSTEM",
                )
                session.add(ev_created)

                if actual_pk_dt:
                    ev_pk = ShipmentEvent(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        shipment_id=shipment.id,
                        event_type="PICKUP_CONFIRMED",
                        description=f"Consignment loaded and checked out of {orig_city} facility.",
                        occurred_at=actual_pk_dt,
                        location_name=f"{orig_city}, {orig_state}",
                        source="DRIVER_APP",
                    )
                    session.add(ev_pk)

                if actual_deliv_dt:
                    ev_deliv = ShipmentEvent(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        shipment_id=shipment.id,
                        event_type="DELIVERY_CONFIRMED",
                        description=f"Delivered to consignee dock at {dest_city}.",
                        occurred_at=actual_deliv_dt,
                        location_name=f"{dest_city}, {dest_state}",
                        source="DRIVER_APP",
                    )
                    session.add(ev_deliv)

                    # Add Proof of Delivery
                    pod = ProofOfDelivery(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        shipment_id=shipment.id,
                        signed_by_name="Raghavendra Rao",
                        signed_by_designation="Receiving Supervisor",
                        signed_at=actual_deliv_dt,
                        signature_image_url="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='60' viewBox='0 0 220 60'><rect width='220' height='60' fill='%23FFF9F1'/><path d='M18 42 C36 16, 54 48, 76 26 C92 10, 110 44, 134 28 C154 15, 174 38, 202 24' fill='none' stroke='%23253447' stroke-width='2.5' stroke-linecap='round'/></svg>",
                        document_url=None,
                        verification_status=PODVerificationStatus.VERIFIED,
                        verified_at=actual_deliv_dt + timedelta(minutes=10),
                    )
                    session.add(pod)

                # Add Exceptions if flagged
                if trk_num == "SHP-2026-9023":
                    exc = ExceptionRecord(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        shipment_id=shipment.id,
                        exception_type=ExceptionType.MISSED_PICKUP,
                        severity=ExceptionSeverity.CRITICAL,
                        status=ExceptionStatus.OPEN,
                        title="Transporter Missed Scheduled Pickup Window",
                        description="Titan Heavy Haul failed to arrive within the 2-hour commitment window. Driver unreachable.",
                        reported_at=sched_pk_dt + timedelta(hours=2, minutes=15),
                    )
                    session.add(exc)

                elif trk_num == "SHP-2026-9024":
                    exc = ExceptionRecord(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        shipment_id=shipment.id,
                        exception_type=ExceptionType.VEHICLE_BREAKDOWN,
                        severity=ExceptionSeverity.HIGH,
                        status=ExceptionStatus.RECOVERY_IN_PROGRESS,
                        title="Tractor Engine Coolant Leak on Highway",
                        description="Vehicle halted at Mile Marker 142 on I-65 South. Service tow dispatched.",
                        reported_at=now - timedelta(hours=3),
                    )
                    session.add(exc)

                elif trk_num == "SHP-2026-9025":
                    exc = ExceptionRecord(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        shipment_id=shipment.id,
                        exception_type=ExceptionType.DELAYED_PICKUP,
                        severity=ExceptionSeverity.MEDIUM,
                        status=ExceptionStatus.INVESTIGATING,
                        title="Loading Gate Congestion Exceeding 90 Minutes",
                        description="Vehicle arrived on time but delayed at staging queue due to gate congestion.",
                        reported_at=now - timedelta(hours=6),
                    )
                    session.add(exc)

                seeded_count += 1

            await session.commit()
            print(f"✅ Successfully seeded {seeded_count} shipments with full operational records!")


if __name__ == "__main__":
    asyncio.run(seed_data())
