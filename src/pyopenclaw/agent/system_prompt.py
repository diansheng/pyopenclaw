from datetime import datetime
from typing import List, Dict, Any
from pyopenclaw.session.manager import Session

def build_system_prompt(session: Session, tools: List[Dict[str, Any]] = None) -> str:
    base = _load_base_prompt()
    
    # Inject variables
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = base.replace("{datetime}", now)
    prompt = prompt.replace("{session_id}", session.id)
    prompt = prompt.replace("{channel}", session.channel)
    
    if tools:
        prompt = _inject_tool_descriptions(prompt, tools)
        
    return prompt

def _load_base_prompt() -> str:
    # Normally read from file. For MVP, inline.
    return """
You are PyOpenClaw, an autonomous AI agent running locally.
Current time: {datetime}
Session ID: {session_id}
Channel: {channel}

You have access to the following tools to help the user.
Use them whenever necessary. Do not hallucinate capabilities you don't have.
"""

def _inject_tool_descriptions(base: str, tools: List[Dict[str, Any]]) -> str:
    descriptions = []
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        descriptions.append(f"- {name}: {desc}")
        
    return base + "\n\nAvailable Tools:\n" + "\n".join(descriptions)
