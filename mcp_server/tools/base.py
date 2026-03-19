from abc import ABC, abstractmethod
from typing import Any
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

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON Schema for the tool's arguments."""

    @abstractmethod
    async def run(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute the tool and return MCP content blocks."""

    def as_mcp_tool(self) -> Tool:
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
        )
