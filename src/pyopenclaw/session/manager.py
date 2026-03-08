import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List

from pyopenclaw.config import AppConfig
from pyopenclaw.session.conversation_store import ConversationStore
from pyopenclaw.session.lane_queue import LaneQueue
from pyopenclaw.session.compactor import Compactor, CompactorConfig
from pyopenclaw.channels.base import InboundMessage

logger = logging.getLogger(__name__)

@dataclass
class Session:
    id: str
    channel: str
    sender_id: str
    lane_queue: LaneQueue
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

class SessionManager:
    def __init__(
        self,
        config: AppConfig,
        store: ConversationStore,
        compactor: Compactor,
    ):
        self.config = config
        self.store = store
        self.compactor = compactor
        self._active_sessions: Dict[str, Session] = {}
        # Also map (channel, sender_id) -> session_id for fast lookup
        self._channel_sender_map: Dict[str, str] = {}

    async def resolve(self, message: InboundMessage) -> Session:
        key = f"{message.channel}:{message.sender_id}"
        if key in self._channel_sender_map:
            session_id = self._channel_sender_map[key]
            if session_id in self._active_sessions:
                return self._active_sessions[session_id]

        # Not found, create new
        return await self.create(message.channel, message.sender_id)

    async def create(self, channel: str, sender_id: str, parent_id: Optional[str] = None) -> Session:
        session_id = uuid.uuid4().hex
        lane_queue = LaneQueue(session_id=session_id, mode="serial")
        
        session = Session(
            id=session_id,
            channel=channel,
            sender_id=sender_id,
            lane_queue=lane_queue,
            parent_id=parent_id
        )
        
        self._active_sessions[session_id] = session
        self._channel_sender_map[f"{channel}:{sender_id}"] = session_id
        
        logger.info(f"Created new session {session_id} for {channel}:{sender_id}")
        return session

    async def get(self, session_id: str) -> Optional[Session]:
        return self._active_sessions.get(session_id)

    async def persist_turn(self, session: Session, user_msg: InboundMessage, assistant_reply: str) -> None:
        await self.store.append_turn(session.id, user_msg.text, assistant_reply)
        
        # Check compaction
        # We need history length. This is a bit inefficient to query every turn if history is long.
        # But for MVP it's okay.
        # Ideally store keeps a count.
        history = await self.store.get_history(session.id, max_turns=9999)
        if self.compactor.should_compact(len(history)):
            # This requires ModelInvoker which is not passed here.
            # Design doc says: `async def persist_turn(self, session: Session, user_msg: InboundMessage, assistant_reply: str) -> None: ...`
            # And compactor calls `invoker.invoke`.
            # So `persist_turn` needs `invoker` passed in? Or `SessionManager` has it?
            # Design doc section 10.2 doesn't show `invoker` in `__init__`.
            # But `compactor.compact` takes `invoker`.
            # Maybe `persist_turn` just triggers it, or we pass invoker to `persist_turn`.
            # I'll modify `persist_turn` to accept optional `invoker`.
            pass

    async def close(self):
        # Clean up queues
        for session in self._active_sessions.values():
            await session.lane_queue.drain()
