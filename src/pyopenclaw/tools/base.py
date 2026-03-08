from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel
from dataclasses import dataclass, field

@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolCall:
    name: str
    id: str
    arguments: Dict[str, Any]

class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    async def run(self, args: Dict[str, Any]) -> ToolResult:
        pass

    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """Returns OpenAI-compatible function schema."""
        pass
