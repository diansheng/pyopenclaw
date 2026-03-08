from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime

@dataclass
class MemoryHit:
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MemoryRecord:
    id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
