import os
import shutil
from pathlib import Path
from typing import Dict, Any
from pyopenclaw.config import ToolConfig
from pyopenclaw.tools.base import Tool, ToolResult

class FileSystemTool(Tool):
    name = "filesystem"
    description = "Read, write, list, and delete files."

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
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list", "delete"],
                        "description": "The file operation to perform"
                    },
                    "path": {
                        "type": "string",
                        "description": "The file or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write (required for write operation)"
                    }
                },
                "required": ["operation", "path"]
            }
        }

    async def run(self, args: Dict[str, Any]) -> ToolResult:
        op = args.get("operation")
        path_str = args.get("path")
        content = args.get("content")

        try:
            path = self._validate_path(path_str)
            
            if op == "read":
                if not path.exists():
                    return ToolResult(success=False, output="", error=f"File not found: {path}")
                if not path.is_file():
                    return ToolResult(success=False, output="", error=f"Path is not a file: {path}")
                return ToolResult(success=True, output=path.read_text())
                
            elif op == "write":
                if content is None:
                    return ToolResult(success=False, output="", error="Content required for write operation")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return ToolResult(success=True, output=f"Successfully wrote to {path}")
                
            elif op == "list":
                if not path.exists():
                    return ToolResult(success=False, output="", error=f"Directory not found: {path}")
                if not path.is_dir():
                    return ToolResult(success=False, output="", error=f"Path is not a directory: {path}")
                items = [p.name for p in path.iterdir()]
                return ToolResult(success=True, output="\n".join(items))
                
            elif op == "delete":
                if not path.exists():
                     return ToolResult(success=False, output="", error=f"Path not found: {path}")
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                return ToolResult(success=True, output=f"Successfully deleted {path}")
                
            else:
                return ToolResult(success=False, output="", error=f"Unknown operation: {op}")
                
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _validate_path(self, path_str: str) -> Path:
        path = Path(path_str).expanduser().resolve()
        
        # Check if allowed
        allowed = False
        for allowed_path in self.config.allowed_paths:
            allowed_root = Path(allowed_path).expanduser().resolve()
            # Allow exact match or child
            # Note: `path in allowed_root.parents` checks if allowed_root is parent of path? No.
            # `allowed_root in path.parents` checks if allowed_root is parent of path.
            if path == allowed_root or allowed_root in path.parents:
                allowed = True
                break
                
        if not allowed:
            raise PermissionError(f"Path {path} is not in allowed paths: {self.config.allowed_paths}")
            
        return path
