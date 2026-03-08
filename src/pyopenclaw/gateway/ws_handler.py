import logging
from typing import Any
from pyopenclaw.gateway.event_bus import EventBus

logger = logging.getLogger(__name__)

class WSHandler:
    def __init__(self, websocket: Any, client_id: str, event_bus: EventBus):
        self.websocket = websocket
        self.client_id = client_id
        self.event_bus = event_bus

    async def handle_frame(self, raw: str) -> None:
        pass

    async def send_frame(self, frame: dict) -> None:
        pass
