import logging
from typing import Any

logger = logging.getLogger(__name__)

class HTTPHandler:
    def __init__(self):
        pass

    async def handle_health(self, request: Any) -> Any:
        return {"status": "ok"}

    async def handle_chat_sse(self, request: Any) -> Any:
        pass
