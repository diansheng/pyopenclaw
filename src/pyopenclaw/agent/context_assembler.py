import json
import logging
from typing import List, Dict, Any
from pyopenclaw.agent.system_prompt import build_system_prompt
from pyopenclaw.memory.manager import MemoryManager
from pyopenclaw.session.manager import SessionManager, Session
from pyopenclaw.channels.base import InboundMessage

logger = logging.getLogger(__name__)

class ContextAssembler:
    def __init__(self, memory_manager: MemoryManager, session_manager: SessionManager):
        self.memory_manager = memory_manager
        self.session_manager = session_manager

    async def build(self, session: Session, message: InboundMessage, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        messages = []
        
        # System Prompt
        system_prompt = build_system_prompt(session, tools)
        messages.append({"role": "system", "content": system_prompt})
        
        # Memory Injection
        await self._inject_memory_hits(messages, message.text)
        
        # Session History
        await self._inject_session_history(messages, session)
        
        # User Message
        messages.append({"role": "user", "content": message.text})
        
        return messages

    async def _inject_memory_hits(self, messages: List[Dict[str, Any]], query: str) -> None:
        try:
            hits = await self.memory_manager.search(query, top_k=5)
            if hits:
                memory_block = "Relevant Memories:\n"
                for hit in hits:
                    memory_block += f"- {hit.content} (score: {hit.score:.2f})\n"
                
                messages.append({"role": "system", "content": memory_block})
        except Exception as e:
            logger.error(f"Memory search failed: {e}")

    async def _inject_session_history(self, messages: List[Dict[str, Any]], session: Session) -> None:
        try:
            history = await self.session_manager.store.get_history(session.id, max_turns=20)
            
            for turn in history:
                if turn.user_text == "[System Summary]":
                    messages.append({"role": "system", "content": f"Previous conversation summary: {turn.assistant_text}"})
                else:
                    if turn.user_text:
                        messages.append({"role": "user", "content": turn.user_text})
                    if turn.assistant_text:
                        messages.append({"role": "assistant", "content": turn.assistant_text})
        except Exception as e:
            logger.error(f"Failed to load session history: {e}")
