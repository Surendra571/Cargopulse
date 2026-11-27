from app.services.integrations.adapters.base import BaseTransporterAdapter
from app.services.integrations.adapters.generic import GenericWebhookAdapter
from app.services.integrations.adapters.samsara import SamsaraTelematicsAdapter
from app.services.integrations.adapters.intangles import IntanglesTelematicsAdapter
from app.services.integrations.adapters.erp import CustomERPAdapter
from app.services.integrations.adapters.registry import adapter_registry, AdapterRegistry

__all__ = [
    "BaseTransporterAdapter",
    "GenericWebhookAdapter",
    "SamsaraTelematicsAdapter",
    "IntanglesTelematicsAdapter",
    "CustomERPAdapter",
    "adapter_registry",
    "AdapterRegistry",
]
