import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("cargopulse.websocket")


class TrackingWebSocketManager:
    """
    Manages live WebSocket subscriptions for real-time shipment milestone and tracking feeds.
    Maintains thread-safe and async-safe subscription registries per shipment and organization.
    """

    def __init__(self):
        # shipment_id -> set of active WebSockets
        self._shipment_connections: Dict[str, Set[WebSocket]] = {}
        # organization_id -> set of active WebSockets
        self._org_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect_shipment(self, websocket: WebSocket, shipment_id: str, org_id: str):
        """Accepts and registers a client WebSocket for a specific shipment."""
        await websocket.accept()
        async with self._lock:
            if shipment_id not in self._shipment_connections:
                self._shipment_connections[shipment_id] = set()
            self._shipment_connections[shipment_id].add(websocket)

            if org_id not in self._org_connections:
                self._org_connections[org_id] = set()
            self._org_connections[org_id].add(websocket)

        logger.info(f"WebSocket client connected to shipment {shipment_id} (org {org_id})")

    async def disconnect_shipment(self, websocket: WebSocket, shipment_id: str, org_id: str):
        """Removes a disconnected client WebSocket from registries."""
        async with self._lock:
            if shipment_id in self._shipment_connections:
                self._shipment_connections[shipment_id].discard(websocket)
                if not self._shipment_connections[shipment_id]:
                    del self._shipment_connections[shipment_id]

            if org_id in self._org_connections:
                self._org_connections[org_id].discard(websocket)
                if not self._org_connections[org_id]:
                    del self._org_connections[org_id]

        logger.info(f"WebSocket client disconnected from shipment {shipment_id}")

    async def broadcast_shipment_update(self, shipment_id: str, data: dict):
        """
        Broadcasts a live milestone/telematics update event to all subscribers of the shipment.
        """
        async with self._lock:
            targets = list(self._shipment_connections.get(str(shipment_id), []))

        if not targets:
            return

        payload = json.dumps(data, default=str)
        dead_connections: List[WebSocket] = []

        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send to client on shipment {shipment_id}: {e}")
                dead_connections.append(ws)

        if dead_connections:
            async with self._lock:
                if str(shipment_id) in self._shipment_connections:
                    for dead in dead_connections:
                        self._shipment_connections[str(shipment_id)].discard(dead)

    async def broadcast_org_update(self, org_id: str, data: dict):
        """
        Broadcasts a notification to all subscribers within an organization.
        """
        async with self._lock:
            targets = list(self._org_connections.get(str(org_id), []))

        if not targets:
            return

        payload = json.dumps(data, default=str)
        dead_connections: List[WebSocket] = []

        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception as e:
                dead_connections.append(ws)

        if dead_connections:
            async with self._lock:
                if str(org_id) in self._org_connections:
                    for dead in dead_connections:
                        self._org_connections[str(org_id)].discard(dead)


# Global singleton manager instance
tracking_ws_manager = TrackingWebSocketManager()
