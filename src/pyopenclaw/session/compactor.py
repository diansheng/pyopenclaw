from dataclasses import dataclass
from typing import Any, Protocol

class ModelInvokerProtocol(Protocol):
    async def invoke(self, messages: list[dict], tools: list[dict] = None) -> Any: ...

@dataclass
class CompactorConfig:
    enabled: bool = True
    compaction_threshold: int = 40

class Compactor:
    def __init__(self, config: CompactorConfig):
        self.config = config

    def should_compact(self, history_len: int) -> bool:
        if not self.config.enabled:
            return False
        return history_len >= self.config.compaction_threshold

    async def compact(self, session_id: str, history: list[dict], invoker: ModelInvokerProtocol, store: Any) -> None:
        # Construct prompt
        conversation_text = ""
        for turn in history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            conversation_text += f"{role}: {content}\n"
            
        prompt = f"""
Please summarize the following conversation into key facts and context that should be preserved.
Focus on user preferences, important decisions, and current task state.

Conversation:
{conversation_text}

Summary:
"""
        messages = [{"role": "user", "content": prompt}]
        
        # Invoke model
        # Assuming invoker returns a response object with .text attribute or similar
        # For now, let's assume it returns a string or object with text
        response = await invoker.invoke(messages)
        summary_text = getattr(response, "text", str(response))
        
        # Store summary
        await store.compact(session_id, summary_text)
