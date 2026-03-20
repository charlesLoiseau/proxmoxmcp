import json
import logging
from typing import Any, Literal
from .base import BaseTool

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _bytes_to_gb(b: int) -> float:
    return round(b / (1024 ** 3), 2)


def _qemu_disks(proxmox, node: str, vmid: int) -> list[dict]:
    """
    Parse disk info from QEMU VM config.
    Returns list of disks with device, storage, size, and format.
    """
    disks = []
    try:
        config = proxmox.nodes(node).qemu(vmid).config.get()
        disk_keys = [k for k in config if k.startswith(("scsi", "virtio", "ide", "sata"))]
        for key in disk_keys:
            value = config[key]
            # Skip cd-rom drives and non-disk entries
            if "media=cdrom" in value or value == "none":
                continue
            # Format: storage:vm-100-disk-0,size=32G,...
            parts = value.split(",")
            storage_disk = parts[0]
            size_str = next((p.split("=")[1] for p in parts if p.startswith("size=")), "N/A")
            storage = storage_disk.split(":")[0] if ":" in storage_disk else "N/A"
            disks.append({
                "device":  key,
                "storage": storage,
                "size":    size_str,
                "raw":     storage_disk,
            })
    except Exception as e:
        logger.error("Failed to get disk config for qemu/%s on %s: %s", vmid, node, e)
    return disks


def _lxc_disks(proxmox, node: str, vmid: int) -> list[dict]:
    """
    Parse disk info from LXC container config.
    Returns list of mount points with storage and size.
    """
    disks = []
    try:
        config = proxmox.nodes(node).lxc(vmid).config.get()
        disk_keys = [k for k in config if k.startswith(("rootfs", "mp"))]
        for key in disk_keys:
            value = config[key]
            parts = value.split(",")
            storage_disk = parts[0]
            size_str = next((p.split("=")[1] for p in parts if p.startswith("size=")), "N/A")
            storage = storage_disk.split(":")[0] if ":" in storage_disk else "N/A"
            disks.append({
                "device":  key,
                "storage": storage,
                "size":    size_str,
                "raw":     storage_disk,
            })
    except Exception as e:
        logger.error("Failed to get disk config for lxc/%s on %s: %s", vmid, node, e)
    return disks


def _storage_usage(proxmox, node: str) -> list[dict]:
    """Return usage stats for every storage pool visible on the node."""
    storages = []
    try:
        for s in proxmox.nodes(node).storage.get():
            total = s.get("total", 0)
            used  = s.get("used",  0)
            avail = s.get("avail", 0)
            storages.append({
                "storage":      s.get("storage"),
                "type":         s.get("type"),
                "total_gb":     _bytes_to_gb(total),
                "used_gb":      _bytes_to_gb(used),
                "avail_gb":     _bytes_to_gb(avail),
                "used_percent": round(used / total * 100, 1) if total else 0,
                "active":       s.get("active", 0) == 1,
            })
    except Exception as e:
        logger.error("Failed to get storage for node %s: %s", node, e)
    return storages


# ── tool ───────────────────────────────────────────────────────────────────────

class ListDisksTool(BaseTool):

    @property
    def name(self) -> str:
        return "list_disks"

    @property
    def description(self) -> str:
        return (
            "List disk information for the Proxmox cluster. "
            "Shows per-VM/container disk devices and sizes, "
            "plus storage pool usage (total, used, available GB) per node. "
            "Optionally filter by a specific VM ID."
        )

    async def run(self, arguments: dict[str, Any]) -> str:
        vmid_filter = arguments.get("vmid")
        result = {}

        logger.info("Fetching disk info (vmid_filter=%s)...", vmid_filter)

        try:
            nodes = self.proxmox.nodes.get()
        except Exception as e:
            logger.error("Failed to fetch nodes: %s", e)
            return f"Error: could not connect to Proxmox — {e}"

        for node_info in nodes:
            node = node_info["node"]
            node_result = {"storage_pools": [], "vms": []}

            # Storage pool usage
            node_result["storage_pools"] = _storage_usage(self.proxmox, node)

            # QEMU VMs
            try:
                vms = self.proxmox.nodes(node).qemu.get()
                for vm in vms:
                    vid = str(vm.get("vmid"))
                    if vmid_filter and vid != str(vmid_filter):
                        continue
                    disks = _qemu_disks(self.proxmox, node, vid)
                    node_result["vms"].append({
                        "type":   "qemu",
                        "vmid":   vid,
                        "name":   vm.get("name", f"vm-{vid}"),
                        "status": vm.get("status"),
                        "disks":  disks,
                    })
                    logger.info("qemu/%s: %d disk(s)", vid, len(disks))
            except Exception as e:
                logger.error("Failed to fetch QEMU VMs on node %s: %s", node, e)

            # LXC containers
            try:
                containers = self.proxmox.nodes(node).lxc.get()
                for ct in containers:
                    vid = str(ct.get("vmid"))
                    if vmid_filter and vid != str(vmid_filter):
                        continue
                    disks = _lxc_disks(self.proxmox, node, vid)
                    node_result["vms"].append({
                        "type":   "lxc",
                        "vmid":   vid,
                        "name":   ct.get("name", f"ct-{vid}"),
                        "status": ct.get("status"),
                        "disks":  disks,
                    })
                    logger.info("lxc/%s: %d disk(s)", vid, len(disks))
            except Exception as e:
                logger.error("Failed to fetch LXC containers on node %s: %s", node, e)

            result[node] = node_result

        return json.dumps(result, indent=2)

    def as_fastmcp_fn(self):
        tool_self = self

        async def list_disks(vmid: str = "") -> str:
            """
            List disk information for the Proxmox cluster.
            Shows per-VM disk devices and sizes, plus storage pool usage per node.
            Optionally pass a vmid to filter to a single VM or container.
            """
            args = {}
            if vmid:
                args["vmid"] = vmid
            return await tool_self.run(args)

        return list_disks