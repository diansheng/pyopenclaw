import logging
from typing import AsyncIterator
from pyopenclaw.agent.context_assembler import ContextAssembler
from pyopenclaw.agent.model_invoker import ModelInvoker
from pyopenclaw.agent.execution_loop import run_execution_loop
from pyopenclaw.tools.engine import ToolEngine
from pyopenclaw.memory.manager import MemoryManager
from pyopenclaw.session.manager import SessionManager, Session
from pyopenclaw.gateway.event_bus import EventBus
from pyopenclaw.channels.base import InboundMessage

logger = logging.getLogger(__name__)

class AgentRuntime:
    def __init__(
        self,
        context_assembler: ContextAssembler,
        model_invoker: ModelInvoker,
        tool_engine: ToolEngine,
        memory_manager: MemoryManager,
        session_manager: SessionManager,
        event_bus: EventBus,
    ):
        self.context_assembler = context_assembler
        self.model_invoker = model_invoker
        self.tool_engine = tool_engine
        self.memory_manager = memory_manager
        self.session_manager = session_manager
        self.event_bus = event_bus

    async def run(self, session: Session, message: InboundMessage) -> str:
        # Build context
        tools = self.tool_engine.list_available()
        initial_context = await self.context_assembler.build(session, message, tools)
        
        # Run execution loop
        final_text, messages = await run_execution_loop(
            initial_context,
            self.model_invoker,
            self.tool_engine
        )
        
        # Persist turn
        await self.session_manager.persist_turn(session, message, final_text)
        
        return final_text

    async def run_streaming(self, session: Session, message: InboundMessage) -> AsyncIterator[str]:
        # For MVP, fallback to non-streaming execution and yield result
        # To support true streaming with tool use, execution_loop needs refactoring
        final_text = await self.run(session, message)
        yield final_text
