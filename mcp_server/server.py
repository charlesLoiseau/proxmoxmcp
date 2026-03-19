from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import load_config
from .client import get_client
from .tools import load_tools


async def create_server():
    cfg = load_config()
    proxmox = get_client(cfg)
    tools = load_tools(proxmox)

    # Index by name for fast dispatch
    tool_map = {t.name: t for t in tools}

    app = Server("proxmox-mcp")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [t.as_mcp_tool() for t in tools]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        tool = tool_map.get(name)
        if not tool:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        try:
            return await tool.run(arguments)
        except Exception as exc:
            return [TextContent(type="text", text=f"Error running '{name}': {exc}")]

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
