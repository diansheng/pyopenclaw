import json
import logging
from typing import List, Dict, Any, Tuple
from pyopenclaw.agent.model_invoker import ModelInvoker, ModelResponse
from pyopenclaw.agent.tool_call_parser import parse_tool_calls_from_response, format_tool_result_for_context
from pyopenclaw.tools.engine import ToolEngine

logger = logging.getLogger(__name__)

async def run_execution_loop(
    initial_context: List[Dict[str, Any]],
    invoker: ModelInvoker,
    tool_engine: ToolEngine,
    max_iterations: int = 10,
) -> Tuple[str, List[Dict[str, Any]]]:
    
    messages = initial_context.copy()
    tools = tool_engine.list_available()
    
    final_response_text = ""
    
    for i in range(max_iterations):
        logger.info(f"Execution loop iteration {i+1}/{max_iterations}")
        
        # Convert tool definitions to OpenAI format if not already?
        # tool_engine.list_available() returns schemas which are usually dicts.
        # ModelInvoker.invoke expects list of dicts.
        
        response = await invoker.invoke(messages, tools)
        final_response_text = response.text
        
        # Check if we should stop
        if not _should_continue_loop(response):
            break
            
        # Parse tool calls
        tool_calls = parse_tool_calls_from_response(response)
        if not tool_calls:
            break
            
        # Append assistant message with tool calls
        # OpenAI format requires tool_calls field in assistant message
        assistant_msg = {
            "role": "assistant",
            "content": response.text,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}
                } for tc in tool_calls
            ]
        }
        messages.append(assistant_msg)
        
        # Execute tools
        for tc in tool_calls:
            logger.info(f"Executing tool: {tc.name}")
            result = await tool_engine.execute(tc)
            
            tool_msg = format_tool_result_for_context(tc, result)
            messages.append(tool_msg)
            
    return final_response_text, messages

def _should_continue_loop(response: ModelResponse) -> bool:
    return response.finish_reason == "tool_calls" or (response.tool_calls and len(response.tool_calls) > 0)
