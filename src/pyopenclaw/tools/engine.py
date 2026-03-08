import asyncio
from typing import Dict, List, Any, Optional
from pyopenclaw.config import ToolConfig
from pyopenclaw.tools.base import Tool, ToolCall, ToolResult
from pyopenclaw.plugins.registry import PluginRegistry
from pyopenclaw.tools.shell import ShellTool
from pyopenclaw.tools.filesystem import FileSystemTool

class ToolEngine:
    def __init__(self, config: ToolConfig, plugin_registry: PluginRegistry):
        self.config = config
        self.plugin_registry = plugin_registry
        self._tools: Dict[str, Tool] = {}
        
        # Built-in tools
        self._register(ShellTool(config))
        self._register(FileSystemTool(config))

    def _register(self, tool: Tool):
        self._tools[tool.name] = tool

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        tool = self._get_tool(tool_call.name)
        if not tool:
            return ToolResult(
                success=False, 
                output="",
                error=f"Tool not found: {tool_call.name}"
            )

        try:
            return await asyncio.wait_for(
                tool.run(tool_call.arguments), 
                timeout=self.config.timeout_seconds
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False, 
                output="",
                error=f"Tool execution timed out ({self.config.timeout_seconds}s)"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def list_available(self) -> List[Dict[str, Any]]:
        schemas = []
        # Built-in
        for tool in self._tools.values():
            schemas.append(tool.schema)
        
        # TODO: List plugin tools
        return schemas

    def _get_tool(self, name: str) -> Optional[Tool]:
        if name in self._tools:
            return self._tools[name]
        
        # Check plugins
        # Assuming registry has get_item method
        if hasattr(self.plugin_registry, "get_item"):
            plugin_tool = self.plugin_registry.get_item("tool", name)
            if plugin_tool and isinstance(plugin_tool, Tool):
                return plugin_tool
            
        return None
