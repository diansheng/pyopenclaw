import asyncio
import sys
from typing import Dict, Any, Optional
from pyopenclaw.channels.base import ChannelAdapter, InboundMessage, OutboundMessage
from uuid import uuid4

class CLIAdapter(ChannelAdapter):
    channel_name = "cli"

    async def authenticate(self) -> bool:
        return True

    async def read_stdin(self) -> Optional[str]:
        loop = asyncio.get_running_loop()
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return None
            return line.strip()
        except EOFError:
            return None

    def parse_inbound(self, raw: Dict[str, Any]) -> InboundMessage:
        return InboundMessage(
            channel=self.channel_name,
            sender_id="local_cli",
            text=raw.get("text", ""),
            idempotency_key=uuid4().hex
        )

    def format_outbound(self, msg: OutboundMessage) -> Dict[str, Any]:
        return {"text": msg.text}

    async def send(self, formatted: Dict[str, Any]) -> bool:
        print(formatted["text"])
        return True
