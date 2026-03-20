"""
Tool registry
─────────────
To add a new tool:
  1. Create proxmox_mcp/tools/your_tool.py and subclass BaseTool
  2. Import it below and append it to ALL_TOOLS
That's it — the server picks it up automatically.
"""

from proxmoxer import ProxmoxAPI
from .base import BaseTool
from .list_vms import ListVMsTool
from .list_disks import ListDisksTool

# ── Register tools here ────────────────────────────────────────────────────────
_TOOL_CLASSES = [
    ListVMsTool,
    ListDisksTool
]


def load_tools(proxmox: ProxmoxAPI) -> list[BaseTool]:
    """Instantiate every registered tool with the shared Proxmox client."""
    return [cls(proxmox) for cls in _TOOL_CLASSES]
