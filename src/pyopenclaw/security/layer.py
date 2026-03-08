import logging
from dataclasses import dataclass
from typing import Optional

from pyopenclaw.channels.base import InboundMessage
from pyopenclaw.security.device_pairing import DevicePairing
from pyopenclaw.security.acl import ChannelACL
from pyopenclaw.security.injection_firewall import InjectionFirewall, InjectionDetected

logger = logging.getLogger(__name__)

class UnauthorizedDevice(Exception):
    pass

class ACLDenied(Exception):
    pass

@dataclass
class TrustedInboundMessage(InboundMessage):
    """
    Type-safe wrapper for messages that have passed all security checks.
    """
    pass

class SecurityLayer:
    def __init__(
        self,
        device_pairing: DevicePairing,
        acl: ChannelACL,
        firewall: InjectionFirewall,
    ):
        self.device_pairing = device_pairing
        self.acl = acl
        self.firewall = firewall

    async def check(self, message: InboundMessage, client_id: Optional[str] = None) -> TrustedInboundMessage:
        # Step 1: Device Verification
        # Only check device pairing if a client_id is provided (e.g., from WebSocket clients)
        # Server-side channels (Telegram/Slack webhooks) don't have client_id in this context
        if client_id:
            is_approved = await self.device_pairing.is_approved(client_id)
            if not is_approved:
                logger.warning(f"Unauthorized device access attempt: {client_id}")
                raise UnauthorizedDevice(f"Device {client_id} is not approved")

        # Step 2: Channel ACL
        if not self.acl.is_allowed(message.channel, message.sender_id):
            logger.warning(f"ACL denied access for {message.sender_id} on {message.channel}")
            raise ACLDenied(f"Access denied for user {message.sender_id} on channel {message.channel}")

        # Step 3: Prompt Injection Firewall
        # scan() raises InjectionDetected if mode is 'block' and injection is found
        self.firewall.scan(message.text)
        
        # If mode is 'flag' and injection found, we proceed but maybe log it (already logged in scan)
        # The TrustedInboundMessage could carry the scan result metadata if needed, 
        # but for now we just return the message wrapper.
        
        return TrustedInboundMessage(
            channel=message.channel,
            sender_id=message.sender_id,
            text=message.text,
            attachments=message.attachments,
            timestamp=message.timestamp,
            raw=message.raw,
            idempotency_key=message.idempotency_key
        )
