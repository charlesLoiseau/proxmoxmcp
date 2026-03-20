from mcp.server.fastmcp import FastMCP
 
from .config import load_config
from .client import get_client
from .tools import load_tools
 
cfg = load_config()
proxmox = get_client(cfg)
tools = load_tools(proxmox)
 
mcp = FastMCP("proxmox-mcp")
 
# Register every tool onto the FastMCP instance
for tool in tools:
    mcp.add_tool(tool.as_fastmcp_fn())
 