from typing import Dict
from app.services.integrations.adapters.base import BaseTransporterAdapter
from app.services.integrations.adapters.generic import GenericWebhookAdapter
from app.services.integrations.adapters.samsara import SamsaraTelematicsAdapter
from app.services.integrations.adapters.intangles import IntanglesTelematicsAdapter
from app.services.integrations.adapters.erp import CustomERPAdapter


class AdapterRegistry:
    """
    Central registry for resolving transporter and ERP integration adapters.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseTransporterAdapter] = {}
        # Register standard adapters
        self.register(GenericWebhookAdapter())
        self.register(SamsaraTelematicsAdapter())
        self.register(IntanglesTelematicsAdapter())
        self.register(CustomERPAdapter())

    def register(self, adapter: BaseTransporterAdapter) -> None:
        self._adapters[adapter.adapter_type.upper()] = adapter

    def get_adapter(self, adapter_type: str) -> BaseTransporterAdapter:
        normalized = (adapter_type or "GENERIC").upper()
        return self._adapters.get(normalized, self._adapters["GENERIC"])

    def list_adapters(self) -> Dict[str, str]:
        return {k: v.name for k, v in self._adapters.items()}


adapter_registry = AdapterRegistry()
