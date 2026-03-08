import asyncio
import os
from typing import Dict, Any
from pyopenclaw.config import ToolConfig
from pyopenclaw.tools.base import Tool, ToolResult

class ShellTool(Tool):
    name = "shell"
    description = "Execute shell commands in a restricted environment."

    def __init__(self, config: ToolConfig):
        self.config = config

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory"
                    }
                },
                "required": ["command"]
            }
        }

    async def run(self, args: Dict[str, Any]) -> ToolResult:
        if not self.config.shell_enabled:
             return ToolResult(success=False, output="", error="Shell tool is disabled.")
             
        command = args.get("command")
        cwd = args.get("cwd", os.getcwd())
        
        # Sandbox env
        env = self._build_sandboxed_env()
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), 
                timeout=self.config.timeout_seconds
            )
            
            output = stdout.decode() + stderr.decode()
            success = proc.returncode == 0
            
            return ToolResult(
                success=success,
                output=output,
                metadata={"returncode": proc.returncode}
            )
            
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return ToolResult(success=False, output="", error="Command timed out")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _build_sandboxed_env(self) -> Dict[str, str]:
        # Minimal environment
        keep = {'PATH', 'HOME', 'USER', 'LANG', 'LC_ALL'}
        env = {k: os.environ[k] for k in keep if k in os.environ}
        # Explicitly remove sensitive keys if present (though whitelist approach handles most)
        for k in list(env.keys()):
            if any(s in k for s in ['API_KEY', 'TOKEN', 'SECRET', 'PASSWORD']):
                del env[k]
        return env
