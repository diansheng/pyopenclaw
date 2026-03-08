from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

@dataclass
class InboundMessage:
    channel: str
    sender_id: str
    text: str
    attachments: List[Any] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    raw: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""

@dataclass
class OutboundMessage:
    channel: str
    recipient_id: str
    text: str
    markdown: bool = True
    attachments: List[Any] = field(default_factory=list)
    in_reply_to: Optional[str] = None

class ChannelAdapter(ABC):
    channel_name: str

    @abstractmethod
    async def authenticate(self) -> bool: ...

    @abstractmethod
    def parse_inbound(self, raw: Dict[str, Any]) -> InboundMessage: ...

    @abstractmethod
    def format_outbound(self, msg: OutboundMessage) -> Dict[str, Any]: ...

    @abstractmethod
    async def send(self, formatted: Dict[str, Any]) -> bool: ...
