# PyOpenClaw

PyOpenClaw is a self-hosted, persistent AI agent gateway written in Python. It is inspired by **OpenClaw** and faithfully mimics its modular, event-driven architecture to deliver a robust, locally-run agent system.

It turns any LLM into an "agent that acts" rather than a "chatbot that responds." The system runs on your own hardware, accepts messages from multiple channels (CLI, Telegram, Slack, etc.), routes them to an AI agent with access to tools (shell, filesystem), and delivers responses back — all while maintaining persistent memory and conversation state.

## Features

-   **Multi-Channel Support**: Connect via CLI, Telegram, Slack, and Web UI.
-   **Persistent Memory**: Hybrid memory system using SQLite (Vector + FTS5) for long-term recall.
-   **Tool Engine**: Sandboxed execution of Shell commands and Filesystem operations.
-   **Session Management**: Stateful conversations with auto-compaction for long histories.
-   **Security Layer**: Device pairing, Access Control Lists (ACL), and Prompt Injection Firewall.
-   **Plugin System**: Extensible architecture to add new tools and channels.
-   **Local First**: Designed to run on your own infrastructure.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/pyopenclaw.git
    cd pyopenclaw
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install aiosqlite pydantic openai
    # Optional: pip install websockets aiohttp sentence-transformers
    ```

## Configuration

PyOpenClaw manages credentials using a `.env` file, which is not tracked by version control.

### Setup Script

Run the interactive setup script to create your configuration:

```bash
python3 setup_env.py
```

This will create a `.env` file from `.env.example` and prompt you for your API keys.

### Manual Configuration

Alternatively, you can manually copy the example and edit it:

```bash
cp .env.example .env
nano .env
```

### LLM Providers

PyOpenClaw supports multiple LLM providers. By default, it prioritizes:
1.  OpenAI
2.  Anthropic (Claude)
3.  Google Gemini
4.  MiniMax

To configure a specific provider, set the corresponding environment variable:

-   **OpenAI**: `OPENAI_API_KEY`
-   **Anthropic**: `ANTHROPIC_API_KEY`
-   **Google Gemini**: `GEMINI_API_KEY`
-   **MiniMax**: `MINIMAX_API_KEY` (and optional `MINIMAX_GROUP_ID`)

**Note for MiniMax Coding Plan Users:**
If you are using the MiniMax Coding Plan, simply use your plan's API Key as `MINIMAX_API_KEY`. No special OAuth flow is required for the CLI agent.

## Usage

### Running the CLI Agent

You can start the agent in CLI mode to interact with it directly in your terminal.

```bash
# Ensure your virtual environment is active
source .venv/bin/activate

# The agent will load credentials from your .env file automatically
python3 src/pyopenclaw/main.py
```

Once started, type your message and press Enter. Type `exit` to quit.

### Example Interaction

```text
PyOpenClaw Started. Type 'exit' to quit.
> Hello, who are you?
I am PyOpenClaw, an autonomous AI agent running locally. I can help you with tasks using my available tools.

> List the files in the current directory.
[Executing tool: filesystem]
Here are the files:
README.md
src/
tests/
...
```

## Development

### Project Structure

```
src/pyopenclaw/
├── agent/       # Runtime, Invoker, Context Assembly
├── channels/    # Adapters (CLI, Telegram, etc.)
├── gateway/     # WebSocket & HTTP Server
├── memory/      # Vector & FTS Memory System
├── plugins/     # Plugin Registry
├── security/    # ACL, Firewall, Device Pairing
├── session/     # Session Manager & Store
└── tools/       # Tool Engine (Shell, FS)
```

### Developer Guide

#### 1. Setup Development Environment

Install the project with development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs `pytest`, `pytest-cov`, `mypy`, `ruff` and other tools.

#### 2. Running Tests

**Unit & Integration Tests:**
Run the full test suite using pytest:

```bash
pytest
```

**Run specific test file:**
```bash
pytest tests/integration/test_full_flow.py
```

#### 3. Code Coverage

To generate a coverage report:

```bash
pytest --cov=src/pyopenclaw --cov-report=html
```
The HTML report will be available in `tests/coverage/html/index.html`.

#### 4. Type Checking & Linting

```bash
# Type check
mypy src/pyopenclaw

# Linting
ruff check src/pyopenclaw
```

### Running Verification Script

To run the end-to-end verification script (requires no dev deps, just runtime deps):

```bash
python3 tests/verify_full_flow.py
```

## License

[MIT](LICENSE)
