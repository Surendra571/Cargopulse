from fastapi import APIRouter
from app.api.v1.endpoints import (
    analytics,
    audit,
    auth,
    bookings,
    dashboard,
    drivers,
    exceptions,
    health,
    integrations,
    matching,
    organization,
    pickup_monitoring,
    pod,
    shipments,
    tracking,
    transporters,
    vehicles,
    ai_coordinator,
    reconciliation,
)

api_router = APIRouter()

# Include health routes
api_router.include_router(health.router)

# Include authentication routes
api_router.include_router(auth.router)

# Include organization and RBAC routes
api_router.include_router(organization.router)

# Include operations dashboard routes
api_router.include_router(dashboard.router)

# Include shipment management routes
api_router.include_router(shipments.router)

# Include intelligent transporter matching routes
api_router.include_router(matching.router)

# Include transporter booking and dispatch routes
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])

# Include pickup monitoring and accountability routes
api_router.include_router(pickup_monitoring.router)

# Include real-time tracking and milestone routes
api_router.include_router(tracking.router)

# Include digital proof of delivery (ePOD) routes
api_router.include_router(pod.router)

# Include integration reliability engine routes
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])

# Include exception management routes
api_router.include_router(exceptions.router)

# Include transporter, vehicle, and driver routes
api_router.include_router(transporters.router)
api_router.include_router(vehicles.router)
api_router.include_router(drivers.router)

# Include Phase 16 AI Logistics Coordinator routes
api_router.include_router(ai_coordinator.router, prefix="/ai-coordinator", tags=["ai-coordinator"])

# Include Phase 17 Reconciliation Center routes
api_router.include_router(reconciliation.router, prefix="/reconciliation", tags=["reconciliation"])

# Include Phase 18 Analytics & Audit Trail routes
api_router.include_router(analytics.router)
api_router.include_router(audit.router)

