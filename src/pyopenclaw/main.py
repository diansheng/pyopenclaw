import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path if running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyopenclaw.config import AppConfig
from pyopenclaw.gateway.event_bus import EventBus
from pyopenclaw.memory.manager import MemoryManager
from pyopenclaw.session.manager import SessionManager
from pyopenclaw.session.conversation_store import ConversationStore
from pyopenclaw.session.compactor import Compactor
from pyopenclaw.tools.engine import ToolEngine
from pyopenclaw.plugins.registry import PluginRegistry
from pyopenclaw.security.layer import SecurityLayer
from pyopenclaw.security.device_pairing import DevicePairing
from pyopenclaw.security.acl import ChannelACL
from pyopenclaw.security.injection_firewall import InjectionFirewall
from pyopenclaw.agent.runtime import AgentRuntime
from pyopenclaw.agent.model_invoker import ModelInvoker
from pyopenclaw.agent.context_assembler import ContextAssembler
from pyopenclaw.gateway.server import GatewayServer
from pyopenclaw.channels.cli.adapter import CLIAdapter
from pyopenclaw.channels.base import OutboundMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Load Config (defaults for now)
    config = AppConfig()
    
    # Initialize Core Systems
    event_bus = EventBus()
    
    # Memory
    # Expand user path
    db_path = str(Path(config.memory.db_path).expanduser())
    # Ensure dir exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Hack for config injection into MemoryManager
    config.memory.db_path = db_path
    
    memory_manager = MemoryManager(config.memory)
    
    # Initialize DB tables
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with open(schema_path, "r") as f:
                await db.executescript(f.read())
            await db.commit()
        else:
            logger.warning("schema.sql not found, skipping DB init (tables might be missing)")

    # Session
    store = ConversationStore(db_path)
    compactor = Compactor(config.memory.compactor)
    session_manager = SessionManager(config, store, compactor)
    
    # Tools & Plugins
    plugin_registry = PluginRegistry()
    tool_engine = ToolEngine(config.tools, plugin_registry)
    
    # Security
    pairing = DevicePairing(db_path, b"secret_key_placeholder") # Should be from env/config
    acl = ChannelACL(config.security.acl)
    firewall = InjectionFirewall(config.security.firewall)
    security = SecurityLayer(pairing, acl, firewall)
    
    # Agent
    model_invoker = ModelInvoker(config.llm)
    context_assembler = ContextAssembler(memory_manager, session_manager)
    runtime = AgentRuntime(
        context_assembler=context_assembler,
        model_invoker=model_invoker,
        tool_engine=tool_engine,
        memory_manager=memory_manager,
        session_manager=session_manager,
        event_bus=event_bus
    )
    
    # Gateway
    gateway = GatewayServer(config.gateway, event_bus)
    await gateway.start()
    
    # CLI Loop (if enabled)
    # In a real system, CLI would be just another client connecting to Gateway or separate process.
    # For MVP, we run CLI loop here.
    
    cli = CLIAdapter()
    print("PyOpenClaw Started. Type 'exit' to quit.")
    
    try:
        while True:
            user_input = await cli.read_stdin()
            if user_input is None or user_input.lower() == "exit":
                break
                
            if not user_input.strip():
                continue
                
            # Process Message
            try:
                # 1. Adapt
                inbound = cli.parse_inbound({"text": user_input})
                
                # 2. Security
                trusted = await security.check(inbound, client_id="local_cli") # CLI is trusted device?
                # Need to approve local_cli device first or bypass for CLI
                # For now, let's bypass or ensure approved.
                # Or make `check` logic handle "local_cli" specially if needed.
                # But `check` calls `is_approved`.
                # We can auto-approve local_cli on startup.
                await pairing.approve_device("local_cli")
                
                # 3. Session
                session = await session_manager.resolve(trusted)
                
                # 4. Agent
                response_text = await runtime.run(session, trusted)
                
                # 5. Output
                outbound = OutboundMessage(
                    channel="cli",
                    recipient_id="local_cli",
                    text=response_text
                )
                formatted = cli.format_outbound(outbound)
                await cli.send(formatted)
                
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                print(f"Error: {e}")
                
    finally:
        await gateway.stop()
        await session_manager.close()
        await memory_manager.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
