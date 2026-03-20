from abc import ABC, abstractmethod
from typing import Any, Callable
from mcp.types import Tool, TextContent
from proxmoxer import ProxmoxAPI
 
 
class BaseTool(ABC):
    """
    Base class for all Proxmox MCP tools.
 
    To add a new tool:
      1. Create a file in proxmox_mcp/tools/
      2. Subclass BaseTool
      3. Implement `name`, `description`, `input_schema`, and `run`
      4. Register it in proxmox_mcp/tools/__init__.py
    """
 
    def __init__(self, proxmox: ProxmoxAPI):
        self.proxmox = proxmox
 
    @property
    @abstractmethod
    def name(self) -> str:
        """MCP tool name."""
 
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description shown to Claude."""
 
    @abstractmethod
    async def run(self, arguments: dict[str, Any]) -> str:
        """Execute the tool and return a string result."""
 
    def as_fastmcp_fn(self) -> Callable:
        """
        Return a plain async function that FastMCP can register as a tool.
        FastMCP uses the function name, docstring, and signature for introspection.
        """
        tool_self = self
 
        async def fn(**kwargs) -> str:
            return await tool_self.run(kwargs)
 
        fn.__name__ = self.name
        fn.__doc__ = self.description
        return fn
 