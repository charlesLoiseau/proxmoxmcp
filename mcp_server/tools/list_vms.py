import json
import logging
from typing import Any, Literal
from .base import BaseTool

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _bytes_to_gb(b: int) -> float:
    return round(b / (1024 ** 3), 2)


def _qemu_ip(proxmox, node: str, vmid: int) -> str:
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
    except Exception as e:
        logger.debug("Could not get IP for qemu/%s on %s (guest agent may not be running): %s", vmid, node, e)
    return "N/A"


def _lxc_ip(proxmox, node: str, vmid: int) -> str:
    try:
        for iface in proxmox.nodes(node).lxc(vmid).interfaces.get():
            addr = iface.get("inet", "")
            if addr and not addr.startswith("127."):
                return addr.split("/")[0]
    except Exception as e:
        logger.debug("Could not get IP for lxc/%s on %s: %s", vmid, node, e)
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

    async def run(self, arguments: dict[str, Any]) -> str:
        status_filter = arguments.get("status_filter", "all")
        results = []

        logger.info("Fetching nodes from Proxmox...")
        try:
            nodes = self.proxmox.nodes.get()
        except Exception as e:
            logger.error("Failed to fetch nodes: %s", e)
            return f"Error: could not connect to Proxmox — {e}"

        logger.info("Found %d node(s): %s", len(nodes), [n["node"] for n in nodes])

        for node_info in nodes:
            node = node_info["node"]

            # QEMU VMs
            try:
                vms = self.proxmox.nodes(node).qemu.get(full=1)
                logger.info("Node %s: found %d QEMU VM(s)", node, len(vms))
                for vm in vms:
                    running = vm.get("status") == "running"
                    ip = _qemu_ip(self.proxmox, node, vm["vmid"]) if running else "N/A"
                    results.append(_format_vm(vm, node, "qemu", ip))
            except Exception as e:
                logger.error("Failed to fetch QEMU VMs on node %s: %s", node, e)

            # LXC containers
            try:
                containers = self.proxmox.nodes(node).lxc.get()
                logger.info("Node %s: found %d LXC container(s)", node, len(containers))
                for ct in containers:
                    running = ct.get("status") == "running"
                    ip = _lxc_ip(self.proxmox, node, ct["vmid"]) if running else "N/A"
                    results.append(_format_vm(ct, node, "lxc", ip))
            except Exception as e:
                logger.error("Failed to fetch LXC containers on node %s: %s", node, e)

        logger.info("Total VMs/containers collected: %d", len(results))

        if status_filter != "all":
            results = [v for v in results if v["status"] == status_filter]
            logger.info("After filter '%s': %d result(s)", status_filter, len(results))

        if not results:
            return "No VMs found matching the filter."

        return json.dumps(results, indent=2)

    def as_fastmcp_fn(self):
        tool_self = self

        async def list_vms(status_filter: Literal["all", "running", "stopped"] = "all") -> str:
            """
            List all QEMU VMs and LXC containers on the Proxmox cluster.
            Returns name, type, node, status, CPU %, RAM usage, IP address, uptime, and basic I/O counters.
            """
            return await tool_self.run({"status_filter": status_filter})

        return list_vms