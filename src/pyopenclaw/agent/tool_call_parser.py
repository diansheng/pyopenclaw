import json
from typing import List, Dict, Any
from pyopenclaw.agent.model_invoker import ModelResponse
from pyopenclaw.tools.base import ToolCall, ToolResult

def parse_tool_calls_from_response(response: ModelResponse) -> List[ToolCall]:
    tool_calls = []
    if not response.tool_calls:
        return []
        
    for tc in response.tool_calls:
        try:
            name = tc["function"]["name"]
            arguments = json.loads(tc["function"]["arguments"])
            tool_calls.append(ToolCall(
                name=name,
                id=tc["id"],
                arguments=arguments
            ))
        except Exception as e:
            # Log error? Or return partial?
            # For robustness, skip malformed calls
            pass
            
    return tool_calls

def format_tool_result_for_context(tool_call: ToolCall, result: ToolResult) -> Dict[str, Any]:
    content = result.output if result.success else f"ERROR: {result.error}"
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": content
    }
