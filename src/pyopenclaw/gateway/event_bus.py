import asyncio
import uuid
from typing import Dict, Any, Callable, Awaitable

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> str:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = {}
        
        sub_id = str(uuid.uuid4())
        self._subscribers[event_type][sub_id] = handler
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        for event_type in self._subscribers:
            if subscription_id in self._subscribers[event_type]:
                del self._subscribers[event_type][subscription_id]
                return

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        handlers = []
        if event_type in self._subscribers:
            handlers.extend(self._subscribers[event_type].values())
        
        if "*" in self._subscribers:
            handlers.extend(self._subscribers["*"].values())
            
        for handler in handlers:
            # Fire and forget or await? "async pub/sub"
            # Design doc: "asyncio.Queue per subscriber"
            # Here simple await for MVP is okay, or create_task.
            # Ideally create_task to not block publisher.
            asyncio.create_task(handler(payload))
