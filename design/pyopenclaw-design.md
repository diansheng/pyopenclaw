# PyOpenClaw — Detailed Design Document

> **Version:** 0.1-draft  
> **Status:** Design Phase  
> **Purpose:** Python re-implementation of OpenClaw's core architecture as a modular, multi-agent-buildable system  
> **Last Updated:** 2026-03-08

---

## Table of Contents

1. [Vision & Scope](#1-vision--scope)
2. [Overall System Architecture](#2-overall-system-architecture)
3. [Module Hierarchy](#3-module-hierarchy)
4. [Module M1 — Gateway Server](#4-module-m1--gateway-server)
5. [Module M2 — Channel Adapters](#5-module-m2--channel-adapters)
6. [Module M3 — Agent Runtime](#6-module-m3--agent-runtime)
7. [Module M4 — Memory System](#7-module-m4--memory-system)
8. [Module M5 — Tool Engine](#8-module-m5--tool-engine)
9. [Module M6 — Plugin Loader](#9-module-m6--plugin-loader)
10. [Module M7 — Session & State Manager](#10-module-m7--session--state-manager)
11. [Module M8 — Security Layer](#11-module-m8--security-layer)
12. [Cross-Cutting Concerns](#12-cross-cutting-concerns)
13. [Data Schemas & Contracts](#13-data-schemas--contracts)
14. [Test Plans (Per Module)](#14-test-plans-per-module)
15. [Build & Dependency Map](#15-build--dependency-map)
16. [Agent Work Breakdown](#16-agent-work-breakdown)

---

## 1. Vision & Scope

### 1.1 What PyOpenClaw Is

PyOpenClaw is a self-hosted, persistent AI agent gateway written in Python. It turns any LLM into an "agent that acts" rather than a "chatbot that responds." The system runs on your own hardware, accepts messages from multiple channels (Telegram, Slack, WhatsApp, CLI, Web UI), routes them to an AI agent with access to tools (shell, filesystem, browser), and delivers responses back — all while maintaining persistent memory and conversation state.

### 1.2 Design Principles

| Principle | Description |
|-----------|-------------|
| **Modularity First** | Every subsystem is independently testable, replaceable, and deployable |
| **Interface-Driven** | All modules communicate through typed Python Protocols / ABCs |
| **Fail-Isolated** | A crash in one channel adapter must not bring down the agent runtime |
| **Locally Sovereign** | All data (memory, credentials, sessions) stays on-device by default |
| **Plugin-Extensible** | New channels, tools, and LLM providers are added without touching core code |
| **Observable** | Structured JSON logs and a health endpoint at every layer |

### 1.3 What Is In Scope (v1.0)

- WebSocket Gateway server
- Channel adapters: Telegram, Slack, CLI, Web UI (HTTP SSE)
- Agent Runtime with streaming LLM execution loop
- Tool Engine: Shell, Filesystem, HTTP fetch, Python REPL
- Hybrid Memory: SQLite FTS5 + vector embeddings
- Session Manager with lane queues and compaction
- Plugin loader for community extensions
- Security layer: device pairing, channel ACL, prompt-injection firewall
- CLI control tool (`pyoclaw`)

### 1.4 Out of Scope (v1.0)

- WhatsApp / iMessage (requires third-party bridge licensing)
- Voice/audio pipeline
- Multi-tenant cloud hosting
- GUI desktop app

---

## 2. Overall System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         PyOpenClaw Process                         │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Gateway (M1)                             │  │
│  │   WebSocket Server · HTTP REST · SSE · Health Endpoint       │  │
│  │   Port 18389 (WS) · Port 18390 (HTTP)                        │  │
│  └────────────────┬─────────────────────────────────────────────┘  │
│                   │ Unified Message Envelope                        │
│  ┌────────────────▼─────────────────────────────────────────────┐  │
│  │               Channel Adapters (M2)                          │  │
│  │  TelegramAdapter  SlackAdapter  CLIAdapter  WebUIAdapter      │  │
│  └────────────────┬─────────────────────────────────────────────┘  │
│                   │ Normalized InboundMessage                       │
│  ┌────────────────▼─────────────────────────────────────────────┐  │
│  │               Security Layer (M8)                            │  │
│  │   DevicePairing · ChannelACL · PromptInjectionFirewall        │  │
│  └────────────────┬─────────────────────────────────────────────┘  │
│                   │ Trusted InboundMessage                          │
│  ┌────────────────▼─────────────────────────────────────────────┐  │
│  │            Session & State Manager (M7)                      │  │
│  │   SessionResolver · LaneQueue · ConversationStore            │  │
│  └────────────────┬─────────────────────────────────────────────┘  │
│                   │ Session + Assembled Context                     │
│  ┌────────────────▼─────────────────────────────────────────────┐  │
│  │               Agent Runtime (M3)                             │  │
│  │   ContextAssembler · ModelInvoker · ToolCallParser            │  │
│  │   ExecutionLoop · StreamingResponder                          │  │
│  └──────┬───────────────────────────────────────┬───────────────┘  │
│         │ Tool Requests                          │ Memory Queries   │
│  ┌──────▼──────────────┐              ┌──────────▼────────────────┐ │
│  │   Tool Engine (M5)  │              │   Memory System (M4)      │ │
│  │  Shell · FS · HTTP  │              │  ShortTerm · LongTerm      │ │
│  │  PythonREPL · Sub   │              │  VectorStore · FTS5        │ │
│  │  AgentSpawn         │              │  MemoryWriter · Indexer    │ │
│  └─────────────────────┘              └───────────────────────────┘ │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                Plugin Loader (M6)                            │  │
│  │   PluginDiscovery · SchemaValidator · HotLoader              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 2.1 Data Flow: Happy Path (Single Message)

```
User (Telegram)
    │  Raw webhook POST
    ▼
TelegramAdapter.parse_inbound()
    │  InboundMessage(channel="telegram", sender_id, text, ts)
    ▼
SecurityLayer.check()
    │  Passes ACL + injection scan → TrustedInboundMessage
    ▼
SessionManager.resolve_session()
    │  Returns Session(id, lane_queue)
    ▼
LaneQueue.enqueue(task)
    │  Serialised, ordered
    ▼
AgentRuntime.run(session, message)
    │  ContextAssembler builds prompt
    │  ModelInvoker streams tokens
    │  ToolCallParser detects tool requests
    │  ToolEngine executes → result injected
    │  (loop until no more tool calls)
    │  FinalResponse
    ▼
SessionManager.persist_turn()
    │  Writes JSONL transcript
    ▼
TelegramAdapter.send_outbound()
    │  Formatted message to Telegram API
    ▼
User (Telegram) receives reply
```

---

## 3. Module Hierarchy

The tree below shows every module decomposed to its atomic functions. Each leaf is a single Python function or method (≤ 50 lines, single responsibility).

```
pyopenclaw/
├── gateway/                     # M1
│   ├── server.py
│   │   ├── GatewayServer.__init__()
│   │   ├── GatewayServer.start()
│   │   ├── GatewayServer.stop()
│   │   ├── GatewayServer._register_routes()
│   │   └── GatewayServer._on_websocket_connect()
│   ├── ws_handler.py
│   │   ├── WSHandler.handle_frame()
│   │   ├── WSHandler.send_frame()
│   │   ├── WSHandler.broadcast()
│   │   └── WSHandler._validate_schema()
│   ├── http_handler.py
│   │   ├── HTTPHandler.handle_chat_sse()
│   │   ├── HTTPHandler.handle_health()
│   │   └── HTTPHandler.handle_canvas()
│   └── event_bus.py
│       ├── EventBus.subscribe()
│       ├── EventBus.publish()
│       └── EventBus.unsubscribe()
│
├── channels/                    # M2
│   ├── base.py
│   │   └── ChannelAdapter (ABC)
│   │       ├── .authenticate()
│   │       ├── .parse_inbound()
│   │       ├── .format_outbound()
│   │       └── .send()
│   ├── telegram/
│   │   ├── adapter.py
│   │   │   ├── TelegramAdapter.authenticate()
│   │   │   ├── TelegramAdapter.parse_inbound()
│   │   │   ├── TelegramAdapter.format_outbound()
│   │   │   └── TelegramAdapter.send()
│   │   └── webhook.py
│   │       ├── start_webhook_server()
│   │       └── parse_telegram_update()
│   ├── slack/
│   │   ├── adapter.py
│   │   │   ├── SlackAdapter.authenticate()
│   │   │   ├── SlackAdapter.parse_inbound()
│   │   │   ├── SlackAdapter.format_outbound()
│   │   │   └── SlackAdapter.send()
│   │   └── events.py
│   │       └── parse_slack_event()
│   ├── cli/
│   │   └── adapter.py
│   │       ├── CLIAdapter.read_stdin()
│   │       ├── CLIAdapter.parse_inbound()
│   │       └── CLIAdapter.format_outbound()
│   └── webui/
│       └── adapter.py
│           ├── WebUIAdapter.parse_inbound()
│           └── WebUIAdapter.stream_outbound_sse()
│
├── agent/                       # M3
│   ├── runtime.py
│   │   ├── AgentRuntime.run()
│   │   └── AgentRuntime.run_streaming()
│   ├── context_assembler.py
│   │   ├── ContextAssembler.build()
│   │   ├── ContextAssembler._inject_system_prompt()
│   │   ├── ContextAssembler._inject_memory_hits()
│   │   └── ContextAssembler._inject_session_history()
│   ├── model_invoker.py
│   │   ├── ModelInvoker.invoke()
│   │   ├── ModelInvoker.invoke_streaming()
│   │   ├── ModelInvoker._select_provider()
│   │   └── ModelInvoker._handle_rate_limit()
│   ├── tool_call_parser.py
│   │   ├── parse_tool_calls_from_response()
│   │   └── format_tool_result_for_context()
│   ├── execution_loop.py
│   │   ├── run_execution_loop()
│   │   └── _should_continue_loop()
│   └── system_prompt.py
│       ├── build_system_prompt()
│       ├── _load_base_prompt()
│       └── _inject_tool_descriptions()
│
├── memory/                      # M4
│   ├── manager.py
│   │   ├── MemoryManager.search()
│   │   ├── MemoryManager.write()
│   │   └── MemoryManager.delete()
│   ├── short_term.py
│   │   ├── ShortTermCache.get()
│   │   ├── ShortTermCache.set()
│   │   └── ShortTermCache.evict_expired()
│   ├── long_term.py
│   │   ├── LongTermStore.upsert()
│   │   ├── LongTermStore.delete()
│   │   └── LongTermStore.get_by_id()
│   ├── vector_store.py
│   │   ├── VectorStore.index()
│   │   ├── VectorStore.search_knn()
│   │   └── VectorStore._embed()
│   ├── fts_store.py
│   │   ├── FTSStore.index()
│   │   └── FTSStore.search()
│   ├── hybrid_search.py
│   │   ├── hybrid_search()
│   │   └── _reciprocal_rank_fusion()
│   ├── embedder.py
│   │   ├── Embedder.embed()
│   │   └── Embedder._select_provider()
│   └── file_watcher.py
│       ├── MemoryFileWatcher.start()
│       └── MemoryFileWatcher._on_change()
│
├── tools/                       # M5
│   ├── engine.py
│   │   ├── ToolEngine.execute()
│   │   ├── ToolEngine.list_available()
│   │   └── ToolEngine._get_tool()
│   ├── base.py
│   │   └── Tool (ABC)
│   │       ├── .name
│   │       ├── .schema()
│   │       └── .run()
│   ├── shell.py
│   │   ├── ShellTool.run()
│   │   ├── _build_sandboxed_env()
│   │   └── _stream_output()
│   ├── filesystem.py
│   │   ├── FileSystemTool.run()
│   │   ├── _read_file()
│   │   ├── _write_file()
│   │   ├── _list_dir()
│   │   └── _validate_path()
│   ├── http_fetch.py
│   │   ├── HTTPFetchTool.run()
│   │   └── _sanitize_url()
│   ├── python_repl.py
│   │   ├── PythonREPLTool.run()
│   │   └── _restricted_exec()
│   └── sub_agent.py
│       ├── SubAgentSpawnTool.run()
│       └── _await_child_result()
│
├── plugins/                     # M6
│   ├── loader.py
│   │   ├── PluginLoader.discover()
│   │   ├── PluginLoader.load()
│   │   └── PluginLoader.unload()
│   ├── validator.py
│   │   └── validate_plugin_manifest()
│   └── registry.py
│       ├── PluginRegistry.register()
│       ├── PluginRegistry.get()
│       └── PluginRegistry.list_all()
│
├── session/                     # M7
│   ├── manager.py
│   │   ├── SessionManager.resolve()
│   │   ├── SessionManager.create()
│   │   ├── SessionManager.get()
│   │   └── SessionManager.persist_turn()
│   ├── lane_queue.py
│   │   ├── LaneQueue.enqueue()
│   │   ├── LaneQueue.dequeue()
│   │   └── LaneQueue.drain()
│   ├── conversation_store.py
│   │   ├── ConversationStore.append_turn()
│   │   ├── ConversationStore.get_history()
│   │   └── ConversationStore.compact()
│   └── compactor.py
│       ├── Compactor.should_compact()
│       └── Compactor.compact()
│
├── security/                    # M8
│   ├── layer.py
│   │   └── SecurityLayer.check()
│   ├── device_pairing.py
│   │   ├── DevicePairing.issue_challenge()
│   │   ├── DevicePairing.verify_challenge()
│   │   ├── DevicePairing.approve_device()
│   │   └── DevicePairing.revoke_device()
│   ├── acl.py
│   │   ├── ChannelACL.is_allowed()
│   │   └── ChannelACL.add_rule()
│   └── injection_firewall.py
│       ├── InjectionFirewall.scan()
│       └── _detect_prompt_override_patterns()
│
└── cli/                         # Control tool
    └── main.py
        ├── cmd_start()
        ├── cmd_stop()
        ├── cmd_status()
        └── cmd_send()
```

---

## 4. Module M1 — Gateway Server

### 4.1 Responsibility

The Gateway is the single entry/exit point for all network traffic. It runs two servers on separate ports:

- **WebSocket server** (port 18389) — for real-time duplex communication with channel adapters and control clients
- **HTTP server** (port 18390) — for SSE chat streams, the canvas endpoint, and health/metrics

### 4.2 File: `gateway/server.py`

#### Class: `GatewayServer`

```python
class GatewayServer:
    def __init__(self, config: GatewayConfig, event_bus: EventBus): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def _register_routes(self) -> None: ...
    async def _on_websocket_connect(self, websocket, path) -> None: ...
```

**`__init__(config, event_bus)`**
- Stores config (ports, SSL cert paths, allowed origins)
- Holds reference to the EventBus for publishing gateway events
- Initialises empty `_connected_clients: dict[str, WSHandler]`

**`start()`**
- Starts the WebSocket server via `websockets.serve()`
- Starts the HTTP server via `aiohttp.web.Application`
- Calls `_register_routes()`
- Publishes `gateway.started` event

**`stop()`**
- Sends `{"type": "server_shutdown"}` to all connected WS clients
- Closes all WS connections gracefully
- Stops HTTP and WS servers
- Publishes `gateway.stopped` event

**`_register_routes()`**
- Mounts `/health` → `HTTPHandler.handle_health`
- Mounts `/chat` (SSE) → `HTTPHandler.handle_chat_sse`
- Mounts `/__pyoclaw__/canvas/{id}` → `HTTPHandler.handle_canvas`

**`_on_websocket_connect(websocket, path)`**
- Reads the first frame as a `ConnectFrame`
- Validates via `WSHandler._validate_schema()`
- Calls `DevicePairing.verify_challenge()` — rejects on failure
- Registers client in `_connected_clients`
- Delegates ongoing frames to `WSHandler.handle_frame()`
- On disconnect: removes from `_connected_clients`, publishes `client.disconnected`

---

### 4.3 File: `gateway/ws_handler.py`

#### Class: `WSHandler`

```python
class WSHandler:
    def __init__(self, websocket, client_id: str, event_bus: EventBus): ...
    async def handle_frame(self, raw: str) -> None: ...
    async def send_frame(self, frame: dict) -> None: ...
    async def broadcast(self, frame: dict, exclude: set[str]) -> None: ...
    def _validate_schema(self, frame: dict, schema_name: str) -> bool: ...
```

**Frame types handled by `handle_frame`:**

| Frame Type | Dispatches To |
|------------|--------------|
| `agent` | `AgentRuntime.run()` via EventBus |
| `chat` | `AgentRuntime.run_streaming()` via EventBus |
| `health` | Returns heartbeat immediately |
| `cron_register` | `CronScheduler.register()` |
| `session_list` | `SessionManager.list()` |

**`_validate_schema(frame, schema_name)`**
- Looks up JSON schema from `schemas/` directory by name
- Uses `jsonschema.validate()` — returns `False` on `ValidationError`
- Always validates before processing any frame

---

### 4.4 File: `gateway/event_bus.py`

#### Class: `EventBus`

```python
class EventBus:
    def subscribe(self, event_type: str, handler: Callable) -> str: ...
    def unsubscribe(self, subscription_id: str) -> None: ...
    async def publish(self, event_type: str, payload: dict) -> None: ...
```

- In-process async pub/sub using `asyncio.Queue` per subscriber
- `publish()` fans out to all handlers subscribed to `event_type`
- Wildcard subscriptions supported via `"*"` event type
- Each `subscribe()` returns a unique `subscription_id` (UUID4)

---

### 4.5 File: `gateway/http_handler.py`

#### Class: `HTTPHandler`

```python
class HTTPHandler:
    async def handle_health(self, request) -> Response: ...
    async def handle_chat_sse(self, request) -> StreamResponse: ...
    async def handle_canvas(self, request) -> Response: ...
```

**`handle_health(request)`**
- Returns JSON: `{"status": "ok", "uptime_seconds": int, "sessions_active": int}`
- Always returns HTTP 200; if runtime is degraded, returns 200 with `"status": "degraded"`

**`handle_chat_sse(request)`**
- Reads `session_id` and `message` from query params
- Opens SSE stream with `Content-Type: text/event-stream`
- Subscribes to `EventBus` for `agent.token` events on that session
- Streams each token as `data: {token}\n\n`
- Closes stream on `agent.done` event

**`handle_canvas(request)`**
- Reads canvas ID from path params
- Fetches canvas HTML from `CanvasStore`
- Returns with `Content-Type: text/html`

---

## 5. Module M2 — Channel Adapters

### 5.1 Responsibility

Channel adapters translate between platform-native message formats and PyOpenClaw's internal `InboundMessage` / `OutboundMessage` envelope. Each adapter is fully isolated — a crash in the Telegram adapter cannot affect the Slack adapter.

### 5.2 File: `channels/base.py`

#### Abstract Base Class: `ChannelAdapter`

```python
from abc import ABC, abstractmethod

class ChannelAdapter(ABC):
    channel_name: str  # e.g., "telegram", "slack"

    @abstractmethod
    async def authenticate(self) -> bool: ...

    @abstractmethod
    def parse_inbound(self, raw: dict) -> InboundMessage: ...

    @abstractmethod
    def format_outbound(self, msg: OutboundMessage) -> dict: ...

    @abstractmethod
    async def send(self, formatted: dict) -> bool: ...
```

**`InboundMessage` schema:**

```python
@dataclass
class InboundMessage:
    channel: str          # "telegram" | "slack" | "cli" | "webui"
    sender_id: str        # platform-native user/chat ID
    text: str             # raw message text
    attachments: list     # file refs, images
    timestamp: datetime
    raw: dict             # original platform payload (for debugging)
    idempotency_key: str  # platform message ID, used for dedup
```

**`OutboundMessage` schema:**

```python
@dataclass
class OutboundMessage:
    channel: str
    recipient_id: str
    text: str
    markdown: bool = True
    attachments: list = field(default_factory=list)
    in_reply_to: str | None = None
```

---

### 5.3 Telegram Adapter

#### File: `channels/telegram/adapter.py`

```python
class TelegramAdapter(ChannelAdapter):
    channel_name = "telegram"

    def __init__(self, config: TelegramConfig): ...
    async def authenticate(self) -> bool: ...
    def parse_inbound(self, raw: dict) -> InboundMessage: ...
    def format_outbound(self, msg: OutboundMessage) -> dict: ...
    async def send(self, formatted: dict) -> bool: ...
```

**`authenticate()`**
- Calls `GET https://api.telegram.org/bot{token}/getMe`
- Returns `True` if HTTP 200 with `{"ok": true}`
- Logs error and returns `False` on connection failure or bad token

**`parse_inbound(raw)`**
- Extracts `message.from.id` → `sender_id`
- Extracts `message.text` or `message.caption` → `text`
- Extracts `message.message_id` → `idempotency_key`
- Sets `channel = "telegram"`
- Raises `ParseError` if `message` key is missing

**`format_outbound(msg)`**
- Converts `msg.text` to Telegram MarkdownV2 if `msg.markdown` is True
- Returns `{"chat_id": msg.recipient_id, "text": escaped_text, "parse_mode": "MarkdownV2"}`

**`send(formatted)`**
- Posts to `https://api.telegram.org/bot{token}/sendMessage`
- Retries up to 3 times with exponential backoff on HTTP 429
- Returns `True` on success, `False` on permanent failure

#### File: `channels/telegram/webhook.py`

```python
async def start_webhook_server(adapter: TelegramAdapter, port: int) -> None: ...
def parse_telegram_update(body: bytes) -> dict: ...
```

**`start_webhook_server(adapter, port)`**
- Starts an `aiohttp` app on given port
- Registers `POST /webhook/{secret_token}` route
- On each POST: calls `parse_telegram_update()`, then `adapter.parse_inbound()`

**`parse_telegram_update(body)`**
- JSON-decodes body
- Returns dict; raises `ParseError` on invalid JSON or unexpected structure

---

### 5.4 Slack Adapter

#### File: `channels/slack/adapter.py`

```python
class SlackAdapter(ChannelAdapter):
    channel_name = "slack"

    def __init__(self, config: SlackConfig): ...
    async def authenticate(self) -> bool: ...
    def parse_inbound(self, raw: dict) -> InboundMessage: ...
    def format_outbound(self, msg: OutboundMessage) -> dict: ...
    async def send(self, formatted: dict) -> bool: ...
```

**`authenticate()`**
- Calls `slack_sdk.WebClient.auth_test()`
- Returns `True` on success

**`parse_inbound(raw)`**
- Handles both `message` and `app_mention` event types
- Extracts `event.user` → `sender_id`, `event.text` → `text`, `event.ts` → `idempotency_key`
- Strips bot mention from text if present (`<@BOTID>`)

**`format_outbound(msg)`**
- Returns `{"channel": msg.recipient_id, "text": msg.text, "mrkdwn": True}`

**`send(formatted)`**
- Calls `slack_sdk.WebClient.chat_postMessage(**formatted)`
- Returns `True` on success

#### File: `channels/slack/events.py`

```python
def parse_slack_event(body: dict) -> dict: ...
```

- Handles Slack's URL verification challenge (`type: url_verification`)
- Returns the inner `event` dict from an Events API payload
- Raises `ParseError` on unrecognised payload structure

---

### 5.5 CLI Adapter

#### File: `channels/cli/adapter.py`

```python
class CLIAdapter(ChannelAdapter):
    channel_name = "cli"

    async def read_stdin(self) -> str: ...
    def parse_inbound(self, raw: dict) -> InboundMessage: ...
    def format_outbound(self, msg: OutboundMessage) -> dict: ...
    async def send(self, formatted: dict) -> bool: ...
    async def authenticate(self) -> bool: ...
```

**`read_stdin()`**
- Async readline from `sys.stdin` using `asyncio.StreamReader`
- Returns stripped string; returns `None` on EOF

**`parse_inbound(raw)`**
- `raw` is `{"text": str}` from `read_stdin()`
- `sender_id = "local_cli"`, `channel = "cli"`
- `idempotency_key = uuid4().hex`

**`format_outbound(msg)`**
- Strips Markdown syntax for plain terminal output
- Returns `{"text": plain_text}`

**`send(formatted)`**
- Prints to stdout with `print(formatted["text"])`
- Always returns `True`

**`authenticate()`**
- Always returns `True` (CLI is always trusted local)

---

### 5.6 Web UI Adapter

#### File: `channels/webui/adapter.py`

```python
class WebUIAdapter(ChannelAdapter):
    channel_name = "webui"

    def parse_inbound(self, raw: dict) -> InboundMessage: ...
    async def stream_outbound_sse(self, session_id: str, token: str) -> None: ...
    def format_outbound(self, msg: OutboundMessage) -> dict: ...
    async def send(self, formatted: dict) -> bool: ...
    async def authenticate(self) -> bool: ...
```

**`parse_inbound(raw)`**
- `raw` comes from HTTP POST to `/chat`
- Extracts `session_id`, `message`, optional `user_id`
- Returns `InboundMessage` with `channel = "webui"`

**`stream_outbound_sse(session_id, token)`**
- Called by `HTTPHandler.handle_chat_sse()` for each token
- Formats as `data: {"token": token, "session_id": session_id}\n\n`
- Writes to the open SSE `StreamResponse`

---

## 6. Module M3 — Agent Runtime

### 6.1 Responsibility

The Agent Runtime is the brain of the system. It orchestrates the full inference-tool-response loop: assembles context, invokes the LLM, parses tool calls, executes them via the Tool Engine, feeds results back to the model, and emits the final response.

### 6.2 File: `agent/runtime.py`

```python
class AgentRuntime:
    def __init__(
        self,
        context_assembler: ContextAssembler,
        model_invoker: ModelInvoker,
        tool_engine: ToolEngine,
        memory_manager: MemoryManager,
        session_manager: SessionManager,
        event_bus: EventBus,
    ): ...

    async def run(self, session: Session, message: InboundMessage) -> str: ...
    async def run_streaming(self, session: Session, message: InboundMessage) -> AsyncIterator[str]: ...
```

**`run(session, message)`**
- Calls `ContextAssembler.build()` → `context: list[dict]`
- Calls `run_execution_loop(context, session)` → `final_text: str`
- Calls `SessionManager.persist_turn(session, message, final_text)`
- Returns `final_text`

**`run_streaming(session, message)`**
- Same as `run()` but yields token chunks as they arrive
- Publishes `agent.token` events to EventBus per chunk
- Publishes `agent.done` when loop finishes

---

### 6.3 File: `agent/context_assembler.py`

```python
class ContextAssembler:
    def __init__(self, memory_manager: MemoryManager, session_manager: SessionManager): ...

    def build(self, session: Session, message: InboundMessage) -> list[dict]: ...
    def _inject_system_prompt(self, messages: list[dict], session: Session) -> None: ...
    def _inject_memory_hits(self, messages: list[dict], query: str) -> None: ...
    def _inject_session_history(self, messages: list[dict], session: Session) -> None: ...
```

**`build(session, message)`**
- Initialises empty `messages: list[dict]`
- Calls `_inject_system_prompt(messages, session)` — always first
- Calls `_inject_session_history(messages, session)` — most recent N turns
- Calls `_inject_memory_hits(messages, message.text)` — relevant long-term memories
- Appends `{"role": "user", "content": message.text}` last
- Returns `messages`

**`_inject_system_prompt(messages, session)`**
- Calls `build_system_prompt(session)` → system prompt string
- Prepends `{"role": "system", "content": system_prompt}`

**`_inject_memory_hits(messages, query)`**
- Calls `MemoryManager.search(query, top_k=5)` → `list[MemoryHit]`
- If hits exist, formats them as: `"[Memory] {hit.content}"` block
- Inserts as a `system`-role message before the user message

**`_inject_session_history(messages, session)`**
- Fetches `ConversationStore.get_history(session.id, max_turns=20)`
- Appends each turn as `{"role": "user"/"assistant", "content": ...}`

---

### 6.4 File: `agent/model_invoker.py`

```python
class ModelInvoker:
    def __init__(self, config: LLMConfig): ...

    async def invoke(self, messages: list[dict], tools: list[dict]) -> ModelResponse: ...
    async def invoke_streaming(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[str]: ...
    def _select_provider(self) -> LLMProvider: ...
    async def _handle_rate_limit(self, provider: LLMProvider) -> LLMProvider: ...
```

**`invoke(messages, tools)`**
- Calls `_select_provider()` → active provider
- Makes API call with `messages` and `tools` in provider's format
- On HTTP 429: calls `_handle_rate_limit()` → switches to backup provider, retries
- Returns `ModelResponse(text, tool_calls, finish_reason, usage)`

**`_select_provider()`**
- Iterates `config.providers` in priority order
- Skips providers in cooldown (set by `_handle_rate_limit`)
- Returns first healthy provider
- Raises `NoProvidersAvailable` if all are in cooldown

**`_handle_rate_limit(provider)`**
- Adds `provider` to cooldown map with `time.time() + cooldown_seconds`
- Returns next available provider from `_select_provider()`

**`invoke_streaming(messages, tools)`**
- Same as `invoke()` but opens streaming connection
- Yields string chunks as they arrive
- Buffers tool call chunks, emits complete `ToolCall` objects when finished

---

### 6.5 File: `agent/tool_call_parser.py`

```python
def parse_tool_calls_from_response(response: ModelResponse) -> list[ToolCall]: ...
def format_tool_result_for_context(tool_call: ToolCall, result: ToolResult) -> dict: ...
```

**`parse_tool_calls_from_response(response)`**
- Reads `response.tool_calls` (list of raw dicts from LLM API)
- For each: extracts `name`, `id`, `arguments` (JSON-decoded)
- Returns `list[ToolCall(name, id, arguments)]`
- Returns empty list if `response.tool_calls` is None

**`format_tool_result_for_context(tool_call, result)`**
- Returns OpenAI-compatible tool result message:
  ```python
  {
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": result.output if result.success else f"ERROR: {result.error}"
  }
  ```

---

### 6.6 File: `agent/execution_loop.py`

```python
async def run_execution_loop(
    initial_context: list[dict],
    invoker: ModelInvoker,
    tool_engine: ToolEngine,
    max_iterations: int = 10,
) -> tuple[str, list[dict]]: ...

def _should_continue_loop(response: ModelResponse) -> bool: ...
```

**`run_execution_loop(initial_context, invoker, tool_engine, max_iterations)`**
- `messages = initial_context.copy()`
- Loop (up to `max_iterations`):
  1. `response = await invoker.invoke(messages, tool_engine.list_available())`
  2. If `not _should_continue_loop(response)`: break
  3. `tool_calls = parse_tool_calls_from_response(response)`
  4. Append assistant message with tool calls to `messages`
  5. For each `tool_call`: `result = await tool_engine.execute(tool_call)`
  6. Append `format_tool_result_for_context(tc, result)` to `messages`
- Returns `(response.text, messages)`

**`_should_continue_loop(response)`**
- Returns `True` if `response.finish_reason == "tool_calls"`
- Returns `False` if `finish_reason == "stop"` or `"length"`

---

### 6.7 File: `agent/system_prompt.py`

```python
def build_system_prompt(session: Session) -> str: ...
def _load_base_prompt() -> str: ...
def _inject_tool_descriptions(base: str, tools: list[dict]) -> str: ...
```

**`build_system_prompt(session)`**
- Loads base prompt via `_load_base_prompt()`
- Injects current datetime, session ID, channel name
- Appends tool descriptions from `_inject_tool_descriptions()`
- Returns complete system prompt string

**`_load_base_prompt()`**
- Reads `prompts/system_base.md` from package data
- Returns content as string
- Raises `FileNotFoundError` with helpful message if missing

**`_inject_tool_descriptions(base, tools)`**
- Appends a `## Available Tools` section to base
- Lists each tool's name and one-line description
- Returns modified string

---

## 7. Module M4 — Memory System

### 7.1 Responsibility

The Memory System provides the agent with a form of persistent recall across sessions. It is a two-tier architecture: a fast in-process short-term cache (TTL-based), and a durable long-term store backed by SQLite with both FTS5 (keyword) and vector (semantic) indexes.

### 7.2 File: `memory/manager.py`

```python
class MemoryManager:
    def __init__(self, short_term: ShortTermCache, long_term: LongTermStore, searcher: HybridSearcher): ...

    async def search(self, query: str, top_k: int = 5) -> list[MemoryHit]: ...
    async def write(self, content: str, metadata: dict) -> str: ...
    async def delete(self, memory_id: str) -> bool: ...
```

**`search(query, top_k)`**
- First checks `ShortTermCache.get(query)` — returns cached result if fresh
- Falls back to `HybridSearcher.search(query, top_k)`
- Stores result in `ShortTermCache.set(query, results)`
- Returns `list[MemoryHit(id, content, score, metadata)]`

**`write(content, metadata)`**
- Calls `LongTermStore.upsert(content, metadata)` → `memory_id`
- Calls `VectorStore.index(memory_id, content)` (async background task)
- Calls `FTSStore.index(memory_id, content)` (async background task)
- Returns `memory_id`

**`delete(memory_id)`**
- Calls `LongTermStore.delete(memory_id)`
- Calls `VectorStore.delete(memory_id)` and `FTSStore.delete(memory_id)`
- Returns `True` on full success

---

### 7.3 File: `memory/short_term.py`

```python
class ShortTermCache:
    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000): ...

    def get(self, key: str) -> list[MemoryHit] | None: ...
    def set(self, key: str, value: list[MemoryHit]) -> None: ...
    def evict_expired(self) -> int: ...
```

- Backed by `dict[str, (value, expiry_ts)]` in-process
- `get()`: returns `None` if key missing or `time.time() > expiry_ts`
- `set()`: stores `(value, time.time() + ttl_seconds)`, evicts if `len > max_size` (LRU)
- `evict_expired()`: removes all entries past TTL, returns count evicted

---

### 7.4 File: `memory/long_term.py`

```python
class LongTermStore:
    def __init__(self, db_path: str): ...

    async def upsert(self, content: str, metadata: dict) -> str: ...
    async def delete(self, memory_id: str) -> bool: ...
    async def get_by_id(self, memory_id: str) -> MemoryRecord | None: ...
```

- Backed by SQLite table `memories(id TEXT PK, content TEXT, metadata JSON, created_at, updated_at)`
- `upsert()`: inserts or replaces; `memory_id = sha256(content)[:16]`; returns `memory_id`
- `delete()`: hard deletes row; returns `True` if row existed
- `get_by_id()`: returns `MemoryRecord` or `None`

---

### 7.5 File: `memory/vector_store.py`

```python
class VectorStore:
    def __init__(self, db_path: str, embedder: Embedder): ...

    async def index(self, memory_id: str, content: str) -> None: ...
    async def search_knn(self, query: str, top_k: int) -> list[tuple[str, float]]: ...
    async def delete(self, memory_id: str) -> None: ...
    async def _embed(self, text: str) -> list[float]: ...
```

- Uses SQLite with `sqlite-vec` or `hnswlib` for ANN
- `index()`: calls `_embed(content)` → stores `(memory_id, embedding_blob)` in `vec_index` table
- `search_knn()`: embeds query, runs KNN query, returns `list[(memory_id, cosine_similarity)]`
- `_embed()`: delegates to `Embedder.embed()`

---

### 7.6 File: `memory/fts_store.py`

```python
class FTSStore:
    def __init__(self, db_path: str): ...

    async def index(self, memory_id: str, content: str) -> None: ...
    async def search(self, query: str, top_k: int) -> list[tuple[str, float]]: ...
    async def delete(self, memory_id: str) -> None: ...
```

- Uses SQLite's built-in `FTS5` virtual table
- `index()`: `INSERT OR REPLACE INTO memories_fts(rowid, content) VALUES (?, ?)`
- `search()`: Uses `MATCH` query with `bm25()` scoring; returns `list[(memory_id, bm25_score)]`

---

### 7.7 File: `memory/hybrid_search.py`

```python
async def hybrid_search(
    query: str,
    vector_store: VectorStore,
    fts_store: FTSStore,
    long_term: LongTermStore,
    top_k: int = 5,
    alpha: float = 0.5,
) -> list[MemoryHit]: ...

def _reciprocal_rank_fusion(
    vec_results: list[tuple[str, float]],
    fts_results: list[tuple[str, float]],
    k: int = 60,
) -> list[tuple[str, float]]: ...
```

**`hybrid_search()`**
- Runs `VectorStore.search_knn()` and `FTSStore.search()` concurrently via `asyncio.gather()`
- Merges with `_reciprocal_rank_fusion()`
- Fetches full content from `LongTermStore.get_by_id()` for top K
- Returns `list[MemoryHit]` sorted by fused score

**`_reciprocal_rank_fusion(vec_results, fts_results, k)`**
- For each result in each list: `score += 1 / (k + rank)`
- Merges scores across both lists by `memory_id`
- Returns sorted `list[(memory_id, fused_score)]`

---

### 7.8 File: `memory/embedder.py`

```python
class Embedder:
    def __init__(self, config: EmbedderConfig): ...

    async def embed(self, text: str) -> list[float]: ...
    def _select_provider(self) -> EmbeddingProvider: ...
```

**`embed(text)`**
- Calls `_select_provider()` → active provider
- Truncates text to provider's max token limit
- Makes API call, returns `list[float]` embedding vector

**`_select_provider()`**
- Returns provider based on `config.provider`: `"openai"`, `"local"`, `"gemini"`, `"voyage"`
- `"local"` uses `sentence-transformers` running in-process

---

### 7.9 File: `memory/file_watcher.py`

```python
class MemoryFileWatcher:
    def __init__(self, watch_dir: str, memory_manager: MemoryManager): ...

    async def start(self) -> None: ...
    async def _on_change(self, event: FileSystemEvent) -> None: ...
```

- Uses `watchfiles` library to watch `watch_dir` for `.md` file changes
- `_on_change()`: reads changed file, calls `MemoryManager.write()` with file content and `{"source": filepath}` metadata
- Debounced: 500ms minimum between re-indexing the same file

---

## 8. Module M5 — Tool Engine

### 8.1 Responsibility

The Tool Engine is the agent's "hands." It provides a registry of executable tools, handles sandboxing and safety checks, and returns structured results. Every tool is an isolated Python class.

### 8.2 File: `tools/engine.py`

```python
class ToolEngine:
    def __init__(self, config: ToolConfig, plugin_registry: PluginRegistry): ...

    async def execute(self, tool_call: ToolCall) -> ToolResult: ...
    def list_available(self) -> list[dict]: ...
    def _get_tool(self, name: str) -> Tool: ...
```

**`execute(tool_call)`**
- Calls `_get_tool(tool_call.name)` — raises `ToolNotFoundError` if missing
- Checks tool policy: raises `ToolDeniedError` if disabled for current session
- Runs `await tool.run(tool_call.arguments)` inside `asyncio.wait_for(timeout=config.tool_timeout)`
- On timeout: returns `ToolResult(success=False, error="Tool execution timed out")`
- On any exception: returns `ToolResult(success=False, error=str(e))`

**`list_available()`**
- Returns list of JSON schemas, one per registered tool, in OpenAI tool-use format

**`_get_tool(name)`**
- Looks up `name` in built-in tools dict, then `PluginRegistry.get(name)`
- Raises `ToolNotFoundError` if not found in either

---

### 8.3 File: `tools/shell.py`

```python
class ShellTool(Tool):
    name = "shell"

    async def run(self, args: dict) -> ToolResult: ...
    def _build_sandboxed_env(self) -> dict: ...
    async def _stream_output(self, proc: asyncio.subprocess.Process) -> str: ...
```

**`run(args)`**
- `command = args["command"]` (required)
- `cwd = args.get("cwd", os.getcwd())`
- Calls `_build_sandboxed_env()` → env dict with restricted PATH
- Spawns subprocess via `asyncio.create_subprocess_shell()`
- Calls `_stream_output(proc)` — collects stdout+stderr, respects `max_output_bytes`
- Returns `ToolResult(success=returncode==0, output=output, metadata={"returncode": returncode})`

**`_build_sandboxed_env()`**
- Starts with a minimal env: `PATH`, `HOME`, `USER`, `LANG`
- Removes sensitive variables: `AWS_*`, `OPENAI_API_KEY`, `*_TOKEN`, etc.
- Returns sanitised env dict

**`_stream_output(proc)`**
- Reads stdout and stderr with `asyncio.wait_for(proc.communicate(), timeout=30)`
- Truncates to `config.max_output_bytes` (default: 10,000 bytes)
- Returns combined string

---

### 8.4 File: `tools/filesystem.py`

```python
class FileSystemTool(Tool):
    name = "filesystem"

    async def run(self, args: dict) -> ToolResult: ...
    def _read_file(self, path: str) -> str: ...
    def _write_file(self, path: str, content: str) -> None: ...
    def _list_dir(self, path: str) -> list[str]: ...
    def _validate_path(self, path: str) -> str: ...
```

**`run(args)`**
- `operation = args["operation"]` — one of `read`, `write`, `list`, `delete`
- `path = _validate_path(args["path"])`
- Dispatches to `_read_file`, `_write_file`, `_list_dir`, or `os.unlink`
- Returns `ToolResult`

**`_validate_path(path)`**
- Resolves to absolute path via `Path(path).resolve()`
- Checks against `config.allowed_paths` allowlist — raises `ToolDeniedError` if outside
- Raises `ToolDeniedError` if path matches `config.denied_patterns` (e.g. `~/.ssh/`)
- Returns resolved path string

---

### 8.5 File: `tools/http_fetch.py`

```python
class HTTPFetchTool(Tool):
    name = "http_fetch"

    async def run(self, args: dict) -> ToolResult: ...
    def _sanitize_url(self, url: str) -> str: ...
```

**`run(args)`**
- `url = _sanitize_url(args["url"])`
- `method = args.get("method", "GET").upper()`
- Uses `aiohttp.ClientSession` with `timeout=aiohttp.ClientTimeout(total=15)`
- Blocks requests to RFC-1918 private IP ranges (SSRF protection)
- Returns `ToolResult(output=response_text, metadata={"status": status_code})`

**`_sanitize_url(url)`**
- Parses with `urllib.parse.urlparse()`
- Raises `ToolDeniedError` if scheme is not `http` or `https`
- Raises `ToolDeniedError` if hostname resolves to a private IP address
- Returns normalised URL string

---

### 8.6 File: `tools/python_repl.py`

```python
class PythonREPLTool(Tool):
    name = "python_repl"

    async def run(self, args: dict) -> ToolResult: ...
    def _restricted_exec(self, code: str, namespace: dict) -> str: ...
```

**`run(args)`**
- `code = args["code"]`
- Runs `_restricted_exec()` in a subprocess (not in-process) for isolation
- Uses `multiprocessing.Process` with `timeout=10` seconds
- Captures stdout/stderr via `io.StringIO` redirection
- Returns `ToolResult(output=captured_output)`

**`_restricted_exec(code, namespace)`**
- Compiles code with `compile(code, "<string>", "exec")`
- Executes in restricted `namespace` that excludes `__builtins__` dangerous calls (`open`, `exec`, `eval`, `__import__` for os/sys/subprocess)
- Returns captured stdout as string

---

### 8.7 File: `tools/sub_agent.py`

```python
class SubAgentSpawnTool(Tool):
    name = "spawn_sub_agent"

    async def run(self, args: dict) -> ToolResult: ...
    async def _await_child_result(self, child_session_id: str, timeout: int) -> str: ...
```

**`run(args)`**
- `task = args["task"]` — the instruction for the child agent
- `timeout = args.get("timeout_seconds", 120)`
- Creates new session via `SessionManager.create(parent_id=current_session.id)`
- Sends task as `InboundMessage` to child session
- Calls `_await_child_result(child_session.id, timeout)` → child's final response
- Returns `ToolResult(output=child_response)`

**`_await_child_result(child_session_id, timeout)`**
- Subscribes to `EventBus` for `agent.done` events matching `child_session_id`
- `asyncio.wait_for(event, timeout=timeout)` — raises `TimeoutError` on expiry
- Returns the final text from the done event

---

## 9. Module M6 — Plugin Loader

### 9.1 Responsibility

Enables zero-core-modification extensibility. Any Python package with a `pyopenclaw.extensions` entry in its metadata is auto-discovered and loaded.

### 9.2 File: `plugins/loader.py`

```python
class PluginLoader:
    def __init__(self, registry: PluginRegistry, validator: PluginValidator): ...

    def discover(self) -> list[PluginManifest]: ...
    def load(self, manifest: PluginManifest) -> bool: ...
    def unload(self, plugin_id: str) -> bool: ...
```

**`discover()`**
- Uses `importlib.metadata.entry_points(group="pyopenclaw.extensions")`
- For each entry point: loads manifest dict, validates via `validate_plugin_manifest()`
- Returns `list[PluginManifest]` for all valid discovered plugins
- Logs warnings (not errors) for invalid manifests, so one bad plugin doesn't block others

**`load(manifest)`**
- Dynamically imports `manifest.module` via `importlib.import_module()`
- Calls `plugin_module.setup(registry)` — plugin registers its tools/adapters/providers
- Calls `PluginRegistry.register(manifest)`
- Returns `True` on success, `False` on `ImportError` or `AttributeError`

**`unload(plugin_id)`**
- Calls `plugin_module.teardown()` if it exists
- Calls `PluginRegistry.deregister(plugin_id)`
- Removes module from `sys.modules`
- Returns `True` on success

---

### 9.3 File: `plugins/validator.py`

```python
def validate_plugin_manifest(raw: dict) -> PluginManifest: ...
```

- Validates against required fields: `id`, `name`, `version`, `module`, `provides` (list of `"tool"` | `"channel"` | `"provider"`)
- Validates `version` matches semver pattern
- Returns `PluginManifest` dataclass or raises `ManifestValidationError`

---

### 9.4 File: `plugins/registry.py`

```python
class PluginRegistry:
    def register(self, manifest: PluginManifest, plugin_obj: object) -> None: ...
    def get(self, name: str, kind: str) -> object | None: ...
    def list_all(self) -> list[PluginManifest]: ...
    def deregister(self, plugin_id: str) -> None: ...
```

- Internal dict: `_registry: dict[str, dict]` keyed by `plugin_id`
- `get(name, kind)`: looks up by `(kind, name)` tuple — e.g., `("tool", "my_custom_tool")`
- Thread-safe via `threading.RLock`

---

## 10. Module M7 — Session & State Manager

### 10.1 Responsibility

Manages the lifecycle of conversations (sessions), ensures ordered processing via per-session lane queues, persists turn-by-turn transcripts, and compacts long conversations to stay within model context limits.

### 10.2 File: `session/manager.py`

```python
class SessionManager:
    def __init__(self, store: ConversationStore, lane_factory: LaneQueueFactory): ...

    async def resolve(self, message: InboundMessage) -> Session: ...
    async def create(self, channel: str, sender_id: str, parent_id: str | None = None) -> Session: ...
    async def get(self, session_id: str) -> Session | None: ...
    async def persist_turn(self, session: Session, user_msg: InboundMessage, assistant_reply: str) -> None: ...
```

**`resolve(message)`**
- Looks up existing session by `(channel, sender_id)` from `_active_sessions` dict
- If not found: calls `create(message.channel, message.sender_id)` → new session
- Returns `Session`

**`create(channel, sender_id, parent_id)`**
- `session_id = uuid4().hex`
- Creates `LaneQueue` for the session
- Creates `Session(id, channel, sender_id, parent_id, lane_queue, created_at)`
- Stores in `_active_sessions`
- Returns `Session`

**`persist_turn(session, user_msg, assistant_reply)`**
- Calls `ConversationStore.append_turn(session.id, user_msg.text, assistant_reply)`
- If `Compactor.should_compact(session)`: calls `Compactor.compact(session)`

---

### 10.3 File: `session/lane_queue.py`

```python
class LaneQueue:
    def __init__(self, session_id: str, mode: str = "serial"): ...

    async def enqueue(self, task: Coroutine) -> asyncio.Task: ...
    async def dequeue(self) -> None: ...
    async def drain(self) -> None: ...
```

- `mode = "serial"`: tasks run one at a time (default for all user sessions)
- `mode = "parallel"`: tasks run concurrently (used for cron jobs)
- Internal `asyncio.Queue` + worker coroutine that runs tasks in order
- `enqueue()`: puts task on queue, returns an `asyncio.Task` future
- `drain()`: waits for all queued tasks to finish (used during shutdown)

---

### 10.4 File: `session/conversation_store.py`

```python
class ConversationStore:
    def __init__(self, db_path: str): ...

    async def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None: ...
    async def get_history(self, session_id: str, max_turns: int = 20) -> list[Turn]: ...
    async def compact(self, session_id: str, summary: str) -> None: ...
```

- Backed by SQLite table `turns(id, session_id, user_text, assistant_text, ts)`
- `append_turn()`: inserts row; also appends line to JSONL transcript file at `transcripts/{session_id}.jsonl`
- `get_history()`: returns last `max_turns` rows, ordered by `ts ASC`
- `compact()`: deletes all turns for session, inserts single summary turn

---

### 10.5 File: `session/compactor.py`

```python
class Compactor:
    def __init__(self, config: CompactorConfig): ...

    def should_compact(self, session: Session) -> bool: ...
    async def compact(self, session: Session, invoker: ModelInvoker, store: ConversationStore) -> None: ...
```

**`should_compact(session)`**
- Checks `len(session.history)` against `config.compaction_threshold` (default: 40 turns)
- Returns `True` if over threshold

**`compact(session, invoker, store)`**
- Fetches full history from `store.get_history(session.id, max_turns=9999)`
- Builds a prompt asking the model to summarise the conversation into key facts
- Calls `invoker.invoke(summary_prompt)` → `summary_text`
- Calls `store.compact(session.id, summary_text)` — replaces history with summary

---

## 11. Module M8 — Security Layer

### 11.1 Responsibility

All messages pass through the Security Layer before reaching the Session Manager. It enforces three independent checks: device/client authenticity, channel-level access control, and prompt injection detection.

### 11.2 File: `security/layer.py`

```python
class SecurityLayer:
    def __init__(
        self,
        device_pairing: DevicePairing,
        acl: ChannelACL,
        firewall: InjectionFirewall,
    ): ...

    async def check(self, message: InboundMessage, client_id: str) -> TrustedInboundMessage: ...
```

**`check(message, client_id)`**
- Step 1: `DevicePairing.verify_challenge(client_id)` — raises `UnauthorizedDevice` on failure
- Step 2: `ChannelACL.is_allowed(message.channel, message.sender_id)` — raises `ACLDenied` on failure
- Step 3: `InjectionFirewall.scan(message.text)` — raises `InjectionDetected` on failure
- Returns `TrustedInboundMessage` (same shape as `InboundMessage`, different type for type safety)

---

### 11.3 File: `security/device_pairing.py`

```python
class DevicePairing:
    def __init__(self, db_path: str, secret_key: bytes): ...

    def issue_challenge(self, client_id: str) -> str: ...
    def verify_challenge(self, client_id: str, signed_nonce: str) -> bool: ...
    def approve_device(self, client_id: str) -> str: ...
    def revoke_device(self, client_id: str) -> bool: ...
```

**`issue_challenge(client_id)`**
- Generates `nonce = secrets.token_hex(32)`
- Stores `(client_id, nonce, expiry=now+60s)` in `challenges` table
- Returns nonce

**`verify_challenge(client_id, signed_nonce)`**
- Looks up stored nonce for `client_id` — fails if expired
- Verifies HMAC: `hmac.compare_digest(expected_sig, signed_nonce)`
- On success: marks device as verified in `devices` table
- Returns `True` on success, `False` on any failure

**`approve_device(client_id)`**
- Inserts `(client_id, approved=True, device_token=uuid4().hex)` into `devices` table
- Returns `device_token`

**`revoke_device(client_id)`**
- Sets `approved=False` for `client_id` in `devices` table
- Returns `True` if row existed

---

### 11.4 File: `security/acl.py`

```python
class ChannelACL:
    def __init__(self, config: ACLConfig): ...

    def is_allowed(self, channel: str, sender_id: str) -> bool: ...
    def add_rule(self, channel: str, sender_id: str, allow: bool) -> None: ...
```

**`is_allowed(channel, sender_id)`**
- Default policy: `config.default_policy` — either `"allow"` or `"deny"`
- Checks `_rules` dict for `(channel, sender_id)` override — explicit rules take precedence
- Checks `(channel, "*")` for channel-wide rules
- Returns `bool`

**`add_rule(channel, sender_id, allow)`**
- Upserts into `_rules: dict[(channel, sender_id), bool]`
- Persists to `acl.json` config file

---

### 11.5 File: `security/injection_firewall.py`

```python
class InjectionFirewall:
    def __init__(self, config: FirewallConfig): ...

    def scan(self, text: str) -> ScanResult: ...
    def _detect_prompt_override_patterns(self, text: str) -> list[str]: ...
```

**`scan(text)`**
- Calls `_detect_prompt_override_patterns(text)` → list of matched pattern names
- If matches exist and `config.mode == "block"`: raises `InjectionDetected(patterns=matches)`
- If `config.mode == "flag"`: returns `ScanResult(clean=False, patterns=matches)` — processing continues with warning injected into system prompt
- Returns `ScanResult(clean=True)` if no matches

**`_detect_prompt_override_patterns(text)`**
- Regex-based detection of patterns including:
  - `ignore (previous|all|above) instructions`
  - `you are now`, `act as`, `pretend you are`
  - `[system]`, `<system>`, `###system###`
  - `forget your instructions`
  - `jailbreak`, `DAN mode`
- Returns list of matched pattern names

---

## 12. Cross-Cutting Concerns

### 12.1 Configuration System

All config is loaded from a single `config.yaml` at startup, validated against a Pydantic `Settings` model, and injected into modules via constructor arguments (no global singletons).

```yaml
# config.yaml
gateway:
  ws_port: 18389
  http_port: 18390

llm:
  providers:
    - name: anthropic
      api_key_env: ANTHROPIC_API_KEY
      model: claude-sonnet-4-20250514
      priority: 1
    - name: openai
      api_key_env: OPENAI_API_KEY
      model: gpt-4o
      priority: 2

channels:
  telegram:
    enabled: true
    token_env: TELEGRAM_BOT_TOKEN
  slack:
    enabled: false

memory:
  db_path: ~/.pyopenclaw/memory.db
  embedder: openai
  short_term_ttl: 300

tools:
  timeout_seconds: 30
  allowed_paths:
    - ~/workspace
  shell:
    enabled: true
  python_repl:
    enabled: true

security:
  acl:
    default_policy: deny
  firewall:
    mode: block
```

---

### 12.2 Logging

- All logs are **structured JSON** via `structlog`
- Every log entry includes: `timestamp`, `level`, `module`, `session_id` (when available), `correlation_id`
- Log levels map to events: DEBUG=frame content, INFO=lifecycle, WARNING=recoverable errors, ERROR=unrecoverable failures
- Sensitive fields (`api_key`, `token`, `password`) are automatically redacted by a `structlog` processor

---

### 12.3 Error Hierarchy

```
PyOpenClawError (base)
├── GatewayError
│   ├── FrameValidationError
│   └── ClientConnectionError
├── ChannelError
│   ├── ParseError
│   └── SendError
├── AgentError
│   ├── ContextAssemblyError
│   └── NoProvidersAvailable
├── MemoryError
│   └── EmbeddingError
├── ToolError
│   ├── ToolNotFoundError
│   ├── ToolDeniedError
│   └── ToolTimeoutError
├── SecurityError
│   ├── UnauthorizedDevice
│   ├── ACLDenied
│   └── InjectionDetected
└── PluginError
    └── ManifestValidationError
```

---

### 12.4 Async Architecture

- All I/O is `async/await` throughout; no blocking calls on the event loop
- CPU-bound tasks (embedding, compaction) run in `asyncio.run_in_executor(ThreadPoolExecutor)`
- All database access uses `aiosqlite`
- LLM API calls use `aiohttp` with connection pooling

---

## 13. Data Schemas & Contracts

### 13.1 WebSocket Frame Schemas

**Connect Frame (client → server):**
```json
{
  "type": "connect",
  "client_id": "string",
  "role": "client | node",
  "signed_nonce": "string"
}
```

**Agent Frame (client → server):**
```json
{
  "type": "agent",
  "idempotency_key": "string",
  "session_id": "string | null",
  "channel": "string",
  "sender_id": "string",
  "text": "string"
}
```

**Token Frame (server → client, streaming):**
```json
{
  "type": "token",
  "session_id": "string",
  "token": "string"
}
```

**Done Frame (server → client):**
```json
{
  "type": "done",
  "session_id": "string",
  "full_text": "string"
}
```

---

### 13.2 Tool Call & Result Contracts

```python
@dataclass
class ToolCall:
    name: str
    id: str
    arguments: dict

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict = field(default_factory=dict)
```

---

### 13.3 Memory Record

```python
@dataclass
class MemoryRecord:
    id: str
    content: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

@dataclass
class MemoryHit:
    id: str
    content: str
    score: float
    metadata: dict
```

---

## 14. Test Plans (Per Module)

### 14.1 Testing Philosophy

- **Unit tests**: test each atomic function in isolation with mocked dependencies
- **Integration tests**: test module-to-module interaction with real SQLite (in-memory)
- **End-to-end tests**: test full message flow from fake channel POST to response delivery
- **Contract tests**: verify every module honours its typed interface (Protocol checks)
- Test framework: `pytest` + `pytest-asyncio` + `respx` (HTTP mocking) + `pytest-mock`

---

### 14.2 M1 — Gateway Server Tests

**Unit Tests (`tests/gateway/test_ws_handler.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| GW-U-01 | `_validate_schema` | Valid connect frame | Returns `True` |
| GW-U-02 | `_validate_schema` | Frame missing `client_id` | Returns `False` |
| GW-U-03 | `handle_frame` | `type: "health"` frame | Returns heartbeat without calling EventBus |
| GW-U-04 | `handle_frame` | `type: "agent"` frame | Publishes `agent.request` to EventBus |
| GW-U-05 | `send_frame` | Dict payload | Serializes to JSON and calls `websocket.send()` |
| GW-U-06 | `broadcast` | Frame + exclude set | Sends to all clients not in exclude set |

**Unit Tests (`tests/gateway/test_http_handler.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| GW-U-07 | `handle_health` | GET /health | Returns 200 JSON with `"status": "ok"` |
| GW-U-08 | `handle_health` | GET /health when degraded | Returns 200 JSON with `"status": "degraded"` |
| GW-U-09 | `handle_chat_sse` | GET /chat with session_id | Returns `text/event-stream` content type |
| GW-U-10 | `handle_canvas` | Unknown canvas ID | Returns 404 |

**Integration Tests (`tests/gateway/test_server_integration.py`)**

| Test ID | Scenario | Expected |
|---------|----------|----------|
| GW-I-01 | Client connects with valid signed nonce | Connection accepted, `client.connected` event fired |
| GW-I-02 | Client connects with invalid nonce | Connection rejected with error frame |
| GW-I-03 | Send `agent` frame → response flows back | Full round-trip with mocked AgentRuntime |
| GW-I-04 | Server `stop()` called with active clients | Graceful disconnect frames sent to all clients |

---

### 14.3 M2 — Channel Adapters Tests

**Unit Tests (`tests/channels/test_telegram_adapter.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| CH-U-01 | `parse_inbound` | Valid Telegram message dict | Returns correct `InboundMessage` fields |
| CH-U-02 | `parse_inbound` | Dict missing `message` key | Raises `ParseError` |
| CH-U-03 | `parse_inbound` | Message with photo but no text | Returns `InboundMessage` with `text=""` |
| CH-U-04 | `format_outbound` | `OutboundMessage` with Markdown | Returns `parse_mode: MarkdownV2` |
| CH-U-05 | `format_outbound` | `OutboundMessage` with `markdown=False` | Returns no `parse_mode` field |
| CH-U-06 | `send` | Mock 429 response | Retries 3x with backoff, returns `False` |
| CH-U-07 | `authenticate` | Mock 200 `{"ok": true}` | Returns `True` |
| CH-U-08 | `authenticate` | Mock 401 response | Returns `False` |

**Unit Tests (`tests/channels/test_slack_adapter.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| CH-U-09 | `parse_inbound` | `app_mention` event | Strips bot mention from text |
| CH-U-10 | `parse_slack_event` | URL verification payload | Returns challenge string |

**Unit Tests (`tests/channels/test_cli_adapter.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| CH-U-11 | `parse_inbound` | `{"text": "hello"}` | Returns `InboundMessage` with `channel="cli"` |
| CH-U-12 | `format_outbound` | Text with Markdown bold | Returns stripped plain text |
| CH-U-13 | `authenticate` | (always) | Returns `True` |

**Contract Tests (`tests/channels/test_adapter_contract.py`)**

| Test ID | Scenario |
|---------|----------|
| CH-C-01 | All adapters implement `ChannelAdapter` ABC (checked via `isinstance`) |
| CH-C-02 | `parse_inbound` on all adapters returns an `InboundMessage` (not subclass, exact type) |

---

### 14.4 M3 — Agent Runtime Tests

**Unit Tests (`tests/agent/test_context_assembler.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| AG-U-01 | `build` | Session with 5-turn history | Messages include history turns |
| AG-U-02 | `build` | Memory manager returns 3 hits | Memory block prepended before user message |
| AG-U-03 | `_inject_system_prompt` | Any session | First message has `role: "system"` |
| AG-U-04 | `build` | Empty history | Returns system + user message only |

**Unit Tests (`tests/agent/test_model_invoker.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| AG-U-05 | `invoke` | Valid messages | Returns `ModelResponse` with text |
| AG-U-06 | `invoke` | Provider returns 429 | Switches to backup provider, retries |
| AG-U-07 | `invoke` | All providers rate-limited | Raises `NoProvidersAvailable` |
| AG-U-08 | `_select_provider` | Provider 1 in cooldown | Returns provider 2 |

**Unit Tests (`tests/agent/test_tool_call_parser.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| AG-U-09 | `parse_tool_calls_from_response` | Response with 2 tool calls | Returns list of 2 `ToolCall` objects |
| AG-U-10 | `parse_tool_calls_from_response` | Response with no tool calls | Returns empty list |
| AG-U-11 | `format_tool_result_for_context` | Failed `ToolResult` | Content starts with `"ERROR:"` |

**Unit Tests (`tests/agent/test_execution_loop.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| AG-U-12 | `run_execution_loop` | Model returns `finish_reason: "stop"` immediately | Loop runs exactly once |
| AG-U-13 | `run_execution_loop` | Model returns tool calls, then stop | Loop runs twice (tool call + final) |
| AG-U-14 | `run_execution_loop` | Model returns tool calls 11 times | Loop stops at `max_iterations=10`, returns last response |
| AG-U-15 | `_should_continue_loop` | `finish_reason: "tool_calls"` | Returns `True` |
| AG-U-16 | `_should_continue_loop` | `finish_reason: "stop"` | Returns `False` |

---

### 14.5 M4 — Memory System Tests

**Unit Tests (`tests/memory/test_short_term.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| MEM-U-01 | `get` | Key present, not expired | Returns value |
| MEM-U-02 | `get` | Key present, expired | Returns `None` |
| MEM-U-03 | `get` | Key absent | Returns `None` |
| MEM-U-04 | `set` | Cache at max_size | Evicts LRU entry |
| MEM-U-05 | `evict_expired` | 3 expired + 2 fresh | Returns 3, leaves 2 |

**Unit Tests (`tests/memory/test_long_term.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| MEM-U-06 | `upsert` | New content | Returns deterministic ID |
| MEM-U-07 | `upsert` | Same content twice | Upserts (no duplicate row) |
| MEM-U-08 | `delete` | Existing ID | Returns `True` |
| MEM-U-09 | `delete` | Non-existing ID | Returns `False` |
| MEM-U-10 | `get_by_id` | Valid ID | Returns `MemoryRecord` |

**Unit Tests (`tests/memory/test_hybrid_search.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| MEM-U-11 | `_reciprocal_rank_fusion` | Overlapping vec + fts results | Overlapping items score higher |
| MEM-U-12 | `_reciprocal_rank_fusion` | One empty list | Returns ranked results from other list |
| MEM-U-13 | `hybrid_search` | Query string | Calls vector and FTS concurrently (mock check) |

**Integration Tests (`tests/memory/test_memory_integration.py`)**

| Test ID | Scenario | Expected |
|---------|----------|----------|
| MEM-I-01 | Write memory, then search for it | Hit appears in top 3 results |
| MEM-I-02 | Write memory, delete it, search | Not in results |
| MEM-I-03 | Short-term cache hit avoids DB call | `LongTermStore.search` not called on second identical query |

---

### 14.6 M5 — Tool Engine Tests

**Unit Tests (`tests/tools/test_shell.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| TOOL-U-01 | `run` | `{"command": "echo hello"}` | Returns `ToolResult(success=True, output="hello\n")` |
| TOOL-U-02 | `run` | `{"command": "exit 1"}` | Returns `ToolResult(success=False)` |
| TOOL-U-03 | `_build_sandboxed_env` | (no input) | Does not contain `OPENAI_API_KEY` |
| TOOL-U-04 | `_stream_output` | Output > max_output_bytes | Returns truncated output |

**Unit Tests (`tests/tools/test_filesystem.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| TOOL-U-05 | `_validate_path` | Path outside allowed_paths | Raises `ToolDeniedError` |
| TOOL-U-06 | `_validate_path` | Path in allowed_paths | Returns resolved abs path |
| TOOL-U-07 | `run` | `operation: "read"`, valid path | Returns file contents |
| TOOL-U-08 | `run` | `operation: "write"`, valid path | Writes file, returns success |

**Unit Tests (`tests/tools/test_http_fetch.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| TOOL-U-09 | `_sanitize_url` | `http://192.168.1.1` | Raises `ToolDeniedError` (private IP) |
| TOOL-U-10 | `_sanitize_url` | `ftp://example.com` | Raises `ToolDeniedError` (bad scheme) |
| TOOL-U-11 | `run` | Valid HTTPS URL (mocked) | Returns `ToolResult` with response body |

**Unit Tests (`tests/tools/test_python_repl.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| TOOL-U-12 | `_restricted_exec` | `print("hello")` | Returns `"hello\n"` |
| TOOL-U-13 | `_restricted_exec` | `import os; os.system("rm -rf /")` | Raises or returns error |
| TOOL-U-14 | `run` | Code that runs > 10 seconds | Returns timeout `ToolResult` |

**Integration Tests (`tests/tools/test_engine_integration.py`)**

| Test ID | Scenario | Expected |
|---------|----------|----------|
| TOOL-I-01 | Execute known tool by name | Returns `ToolResult` |
| TOOL-I-02 | Execute unknown tool name | Returns error `ToolResult` |
| TOOL-I-03 | Plugin-registered tool is callable | Tool found via `PluginRegistry` |

---

### 14.7 M6 — Plugin Loader Tests

**Unit Tests (`tests/plugins/test_validator.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| PLG-U-01 | `validate_plugin_manifest` | Valid manifest dict | Returns `PluginManifest` |
| PLG-U-02 | `validate_plugin_manifest` | Missing `id` field | Raises `ManifestValidationError` |
| PLG-U-03 | `validate_plugin_manifest` | Invalid semver in `version` | Raises `ManifestValidationError` |

**Unit Tests (`tests/plugins/test_loader.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| PLG-U-04 | `load` | Valid plugin with `setup()` | Returns `True`, tool registered |
| PLG-U-05 | `load` | Plugin `setup()` raises | Returns `False`, no crash |
| PLG-U-06 | `unload` | Loaded plugin ID | Returns `True`, removed from registry |
| PLG-U-07 | `discover` | Two valid + one invalid entry point | Returns 2 manifests, logs 1 warning |

---

### 14.8 M7 — Session Manager Tests

**Unit Tests (`tests/session/test_lane_queue.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| SES-U-01 | `enqueue` (serial) | 3 tasks | Tasks run in order (tracked via list) |
| SES-U-02 | `enqueue` (serial) | Task 2 raises exception | Task 3 still runs |
| SES-U-03 | `drain` | Queue with 2 pending tasks | Returns after both complete |

**Unit Tests (`tests/session/test_conversation_store.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| SES-U-04 | `append_turn` | Session ID + texts | Row inserted in DB |
| SES-U-05 | `append_turn` | Session ID | JSONL file updated |
| SES-U-06 | `get_history` | `max_turns=3`, 10 turns stored | Returns last 3 turns |
| SES-U-07 | `compact` | Session with 20 turns | All turns replaced by 1 summary turn |

**Unit Tests (`tests/session/test_compactor.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| SES-U-08 | `should_compact` | Session with 30 turns (threshold=40) | Returns `False` |
| SES-U-09 | `should_compact` | Session with 45 turns (threshold=40) | Returns `True` |
| SES-U-10 | `compact` | Session with history | Calls `invoker.invoke` with summary prompt |

---

### 14.9 M8 — Security Layer Tests

**Unit Tests (`tests/security/test_device_pairing.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| SEC-U-01 | `issue_challenge` | Client ID | Returns 64-char hex nonce |
| SEC-U-02 | `verify_challenge` | Valid HMAC signature | Returns `True` |
| SEC-U-03 | `verify_challenge` | Invalid signature | Returns `False` |
| SEC-U-04 | `verify_challenge` | Expired nonce (>60s) | Returns `False` |
| SEC-U-05 | `revoke_device` | Approved device ID | Returns `True`, device blocked |

**Unit Tests (`tests/security/test_acl.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| SEC-U-06 | `is_allowed` | Default deny, no rule | Returns `False` |
| SEC-U-07 | `is_allowed` | Explicit allow rule for sender | Returns `True` |
| SEC-U-08 | `is_allowed` | Channel-wide deny, sender allow | Sender allow wins |
| SEC-U-09 | `add_rule` | New rule | Persists to `acl.json` |

**Unit Tests (`tests/security/test_injection_firewall.py`)**

| Test ID | Function Tested | Input | Expected |
|---------|----------------|-------|----------|
| SEC-U-10 | `scan` | "Hello, what's the weather?" | Returns `ScanResult(clean=True)` |
| SEC-U-11 | `scan` | "ignore all previous instructions" | Block mode: raises `InjectionDetected` |
| SEC-U-12 | `scan` | "pretend you are an evil AI" | Block mode: raises `InjectionDetected` |
| SEC-U-13 | `_detect_prompt_override_patterns` | Text with `[SYSTEM]` tag | Returns `["system_tag"]` in pattern list |
| SEC-U-14 | `scan` | Injection text, mode=flag | Returns `ScanResult(clean=False)`, no raise |

**Integration Tests (`tests/security/test_security_layer.py`)**

| Test ID | Scenario | Expected |
|---------|----------|----------|
| SEC-I-01 | Valid device, allowed sender, clean text | Returns `TrustedInboundMessage` |
| SEC-I-02 | Invalid device token | Raises `UnauthorizedDevice` |
| SEC-I-03 | Valid device, denied sender | Raises `ACLDenied` |
| SEC-I-04 | Valid device, allowed sender, injection text | Raises `InjectionDetected` |

---

### 14.10 End-to-End Tests

**File: `tests/e2e/test_full_flow.py`**

| Test ID | Scenario | Expected |
|---------|----------|----------|
| E2E-01 | CLI → "echo hello" shell command → response | Response contains "hello" |
| E2E-02 | CLI → question → memory written → second CLI question references first | Memory hit used in second context |
| E2E-03 | Telegram webhook → agent → reply sent back to Telegram API mock | Telegram `sendMessage` called once |
| E2E-04 | WebUI SSE → streaming message | SSE events arrive with token chunks |
| E2E-05 | Two concurrent CLI sessions | Each session's lane queue is independent |
| E2E-06 | Injection attack via Telegram | Message blocked, no agent invocation |
| E2E-07 | LLM provider rate-limited | Fallback provider used transparently |
| E2E-08 | Tool call exceeds timeout | Graceful error in response, session continues |

---

## 15. Build & Dependency Map

### 15.1 Package Structure

```
pyopenclaw/
├── pyproject.toml
├── config.yaml.example
├── prompts/
│   └── system_base.md
├── schemas/
│   ├── connect_frame.json
│   ├── agent_frame.json
│   └── ...
├── src/
│   └── pyopenclaw/
│       ├── __init__.py
│       ├── main.py              ← entrypoint
│       ├── gateway/
│       ├── channels/
│       ├── agent/
│       ├── memory/
│       ├── tools/
│       ├── plugins/
│       ├── session/
│       ├── security/
│       └── cli/
└── tests/
    ├── gateway/
    ├── channels/
    ├── agent/
    ├── memory/
    ├── tools/
    ├── plugins/
    ├── session/
    ├── security/
    └── e2e/
```

### 15.2 Core Dependencies

| Package | Version | Used By |
|---------|---------|---------|
| `websockets` | ^12.0 | M1 Gateway WS server |
| `aiohttp` | ^3.9 | M1 HTTP, M2 Telegram/Slack/HTTPFetchTool |
| `structlog` | ^24.0 | All modules (logging) |
| `pydantic` | ^2.0 | Config validation, data models |
| `aiosqlite` | ^0.20 | M4 Memory, M7 Sessions, M8 Security |
| `jsonschema` | ^4.0 | M1 frame validation, M6 plugin manifests |
| `watchfiles` | ^0.21 | M4 MemoryFileWatcher |
| `sentence-transformers` | ^2.0 | M4 local embedder |
| `slack-sdk` | ^3.0 | M2 Slack adapter |
| `anthropic` | ^0.25 | M3 ModelInvoker (Anthropic provider) |
| `openai` | ^1.0 | M3 ModelInvoker (OpenAI provider) |
| `click` | ^8.0 | CLI control tool |
| `pytest-asyncio` | ^0.23 | Test runner |
| `respx` | ^0.21 | HTTP mocking in tests |

### 15.3 Module Dependency Graph

```
CLI ──────────────────────────────────────► Gateway (M1)
                                                │
                                         Channel Adapters (M2)
                                                │
                                         Security Layer (M8)
                                                │
                                         Session Manager (M7)
                                                │
                                         Agent Runtime (M3)
                                                ├──────────► Tool Engine (M5)
                                                │                │
                                                └──────────► Memory System (M4)
                                                                 │
                                         Plugin Loader (M6) ◄────┘
                                         (provides tools/channels/providers to all)
```

**Build order (no circular deps):**
1. `security`, `session`, `memory` (no internal deps)
2. `tools` (depends on `security`)
3. `plugins` (depends on `tools`, `channels`)
4. `agent` (depends on `memory`, `tools`, `session`)
5. `channels` (no core deps)
6. `gateway` (depends on `channels`, `agent`, `security`, `session`)

---

## 16. Agent Work Breakdown

This section maps each module to an independent agent workstream. Each agent can build and test their module in isolation before integration.

| Agent | Module(s) | Primary Files | Interfaces Consumed | Interfaces Produced |
|-------|-----------|--------------|--------------------|--------------------|
| **Agent A** | M8 Security | `security/` | None | `SecurityLayer.check()` |
| **Agent B** | M7 Session | `session/` | None | `SessionManager`, `LaneQueue`, `ConversationStore` |
| **Agent C** | M4 Memory | `memory/` | None | `MemoryManager.search/write/delete` |
| **Agent D** | M5 Tools | `tools/` | `security/acl.py` (ToolPolicy) | `ToolEngine.execute/list_available` |
| **Agent E** | M6 Plugins | `plugins/` | `tools/`, `channels/base.py` | `PluginRegistry.get/list_all` |
| **Agent F** | M2 Channels | `channels/` | `InboundMessage`, `OutboundMessage` types | `ChannelAdapter` ABC implementations |
| **Agent G** | M3 Agent Runtime | `agent/` | M4 `MemoryManager`, M5 `ToolEngine`, M7 `SessionManager` | `AgentRuntime.run/run_streaming` |
| **Agent H** | M1 Gateway | `gateway/` | M2 `ChannelAdapter`, M3 `AgentRuntime`, M8 `SecurityLayer` | WebSocket server, HTTP server |
| **Agent I** | CLI + Config + E2E | `cli/`, `config.py`, `tests/e2e/` | All modules | Full system entrypoint |

### 16.1 Integration Milestones

1. **Milestone 1:** Agents A + B + C complete → Security + Session + Memory independently testable
2. **Milestone 2:** Agent D complete → Tool execution works with security policy
3. **Milestone 3:** Agents E + F complete → Channel + Plugin layer ready
4. **Milestone 4:** Agent G complete → Full agent loop testable with mock channel
5. **Milestone 5:** Agent H complete → Gateway wired; CLI adapter end-to-end works
6. **Milestone 6:** Agent I complete → E2E suite green; config validated; system shippable

---

*End of PyOpenClaw Design Document v0.1-draft*
