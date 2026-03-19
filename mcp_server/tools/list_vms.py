import json
from typing import Any
from mcp.types import TextContent
from .base import BaseTool


# ── helpers ────────────────────────────────────────────────────────────────────

def _bytes_to_gb(b: int) -> float:
    return round(b / (1024 ** 3), 2)


def _qemu_ip(proxmox, node: str, vmid: int) -> str:
    """Fetch IP via QEMU guest agent. Returns 'N/A' on any failure."""
    try:
        ifaces = proxmox.nodes(node).qemu(vmid).agent("network-get-interfaces").get()
        for iface in ifaces.get("result", []):
            name = iface.get("name", "")
            if name in ("lo", "docker0") or name.startswith("veth"):
                continue
            for addr in iface.get("ip-addresses", []):
                if addr.get("ip-address-type") == "ipv4":
                    ip = addr["ip-address"]
                    if not ip.startswith("127."):
                        return ip
    except Exception:
        pass
    return "N/A"


def _lxc_ip(proxmox, node: str, vmid: int) -> str:
    """Fetch IP from LXC network interfaces. Returns 'N/A' on any failure."""
    try:
        for iface in proxmox.nodes(node).lxc(vmid).interfaces.get():
            addr = iface.get("inet", "")
            if addr and not addr.startswith("127."):
                return addr.split("/")[0]
    except Exception:
        pass
    return "N/A"


def _format_vm(raw: dict, node: str, kind: str, ip: str) -> dict:
    return {
        "type":          kind,
        "node":          node,
        "vmid":          raw.get("vmid"),
        "name":          raw.get("name", f"{kind}-{raw.get('vmid')}"),
        "status":        raw.get("status", "unknown"),
        "cpu_percent":   round(raw.get("cpu", 0) * 100, 2),
        "ram_used_gb":   _bytes_to_gb(raw.get("mem",    0)),
        "ram_total_gb":  _bytes_to_gb(raw.get("maxmem", 0)),
        "ip":            ip,
        "uptime_sec":    raw.get("uptime", 0),
        "disk_read_mb":  round(raw.get("diskread",  0) / 1024 ** 2, 1),
        "disk_write_mb": round(raw.get("diskwrite", 0) / 1024 ** 2, 1),
        "net_in_mb":     round(raw.get("netin",  0) / 1024 ** 2, 1),
        "net_out_mb":    round(raw.get("netout", 0) / 1024 ** 2, 1),
    }


# ── tool ───────────────────────────────────────────────────────────────────────

class ListVMsTool(BaseTool):

    @property
    def name(self) -> str:
        return "list_vms"

    @property
    def description(self) -> str:
        return (
            "List all QEMU VMs and LXC containers on the Proxmox cluster. "
            "Returns name, type, node, status, CPU %, RAM usage, IP address, "
            "uptime, and basic I/O counters."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["all", "running", "stopped"],
                    "default": "all",
                    "description": "Filter VMs by status.",
                }
            },
            "required": [],
        }

    async def run(self, arguments: dict[str, Any]) -> list[TextContent]:
        status_filter = arguments.get("status_filter", "all")
        results = []

        for node_info in self.proxmox.nodes.get():
            node = node_info["node"]

            # QEMU VMs
            try:
                for vm in self.proxmox.nodes(node).qemu.get(full=1):
                    running = vm.get("status") == "running"
                    ip = _qemu_ip(self.proxmox, node, vm["vmid"]) if running else "N/A"
                    results.append(_format_vm(vm, node, "qemu", ip))
            except Exception:
                pass

            # LXC containers
            try:
                for ct in self.proxmox.nodes(node).lxc.get():
                    running = ct.get("status") == "running"
                    ip = _lxc_ip(self.proxmox, node, ct["vmid"]) if running else "N/A"
                    results.append(_format_vm(ct, node, "lxc", ip))
            except Exception:
                pass

        if status_filter != "all":
            results = [v for v in results if v["status"] == status_filter]

        if not results:
            return [TextContent(type="text", text="No VMs found matching the filter.")]

        return [TextContent(type="text", text=json.dumps(results, indent=2))]
