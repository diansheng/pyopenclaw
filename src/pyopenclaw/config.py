from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class ACLConfig(BaseModel):
    default_policy: Literal["allow", "deny"] = "deny"

class FirewallConfig(BaseModel):
    mode: Literal["block", "flag"] = "block"

class SecurityConfig(BaseModel):
    acl: ACLConfig = Field(default_factory=ACLConfig)
    firewall: FirewallConfig = Field(default_factory=FirewallConfig)

class GatewayConfig(BaseModel):
    ws_port: int = 18789
    http_port: int = 18790

class LLMProviderConfig(BaseModel):
    name: str
    api_key_env: str
    model: str
    priority: int

class LLMConfig(BaseModel):
    providers: List[LLMProviderConfig] = Field(default_factory=lambda: [
        LLMProviderConfig(name="openai", api_key_env="OPENAI_API_KEY", model="gpt-4o", priority=1),
        LLMProviderConfig(name="anthropic", api_key_env="ANTHROPIC_API_KEY", model="claude-3-5-sonnet-20240620", priority=2),
        LLMProviderConfig(name="gemini", api_key_env="GEMINI_API_KEY", model="gemini-1.5-pro", priority=3),
        LLMProviderConfig(name="minimax", api_key_env="MINIMAX_API_KEY", model="MiniMax-M2.5", priority=4),
    ])

class ChannelConfig(BaseModel):
    enabled: bool = True
    token_env: Optional[str] = None

class ChannelsConfig(BaseModel):
    telegram: ChannelConfig = Field(default_factory=ChannelConfig)
    slack: ChannelConfig = Field(default_factory=ChannelConfig)

class CompactorConfig(BaseModel):
    enabled: bool = True
    compaction_threshold: int = 40

class MemoryConfig(BaseModel):
    db_path: str = "~/.pyopenclaw/memory.db"
    embedder: str = "openai"
    short_term_ttl: int = 300
    compactor: CompactorConfig = Field(default_factory=CompactorConfig)

class ToolConfig(BaseModel):
    timeout_seconds: int = 30
    allowed_paths: List[str] = Field(default_factory=lambda: ["~/workspace"])
    shell_enabled: bool = True
    python_repl_enabled: bool = True

class TelemetryConfig(BaseModel):
    enabled: bool = True
    service_name: str = "pyopenclaw"
    service_version: str = "0.2.0"
    # ... other telemetry fields

class AppConfig(BaseModel):
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
