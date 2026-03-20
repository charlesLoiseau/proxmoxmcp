import json
import logging
from typing import Any
from .base import BaseTool

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _bytes_to_gb(b: int) -> float:
    return round(b / (1024 ** 3), 2)


def _guest_fsinfo(proxmox, node: str, vmid: str) -> list[dict]:
    """
    Query filesystem usage via QEMU guest agent (get-fsinfo).
    Returns a list of mount points with used/total/free bytes.
    Only works on running VMs with the guest agent installed.
    """
    filesystems = []
    try:
        result = proxmox.nodes(node).qemu(vmid).agent("get-fsinfo").get()
        for fs in result.get("result", []):
            name        = fs.get("name", "")
            mountpoint  = fs.get("mountpoint", "")
            fs_type     = fs.get("type", "")
            total_bytes = fs.get("total-bytes", 0) or 0
            used_bytes  = fs.get("used-bytes",  0) or 0
            free_bytes  = total_bytes - used_bytes

            # Skip pseudo/virtual filesystems
            if fs_type in ("tmpfs", "devtmpfs", "devpts", "sysfs", "proc",
                           "cgroup", "cgroup2", "overlay", "squashfs"):
                continue

            filesystems.append({
                "name":         name,
                "mountpoint":   mountpoint,
                "type":         fs_type,
                "total_gb":     _bytes_to_gb(total_bytes),
                "used_gb":      _bytes_to_gb(used_bytes),
                "free_gb":      _bytes_to_gb(free_bytes),
                "used_percent": round(used_bytes / total_bytes * 100, 1) if total_bytes else 0,
            })
        logger.info("qemu/%s: got fsinfo for %d filesystem(s) via guest agent", vmid, len(filesystems))
    except Exception as e:
        logger.debug("qemu/%s: guest agent fsinfo not available: %s", vmid, e)
    return filesystems


def _storage_pools(proxmox, node: str) -> list[dict]:
    pools = []
    try:
        for s in proxmox.nodes(node).storage.get():
            total = s.get("total", 0)
            used  = s.get("used",  0)
            avail = s.get("avail", 0)
            pools.append({
                "storage":      s.get("storage"),
                "type":         s.get("type"),
                "total_gb":     _bytes_to_gb(total),
                "used_gb":      _bytes_to_gb(used),
                "avail_gb":     _bytes_to_gb(avail),
                "used_percent": round(used / total * 100, 1) if total else 0,
                "active":       s.get("active", 0) == 1,
            })
    except Exception as e:
        logger.error("Failed to get storage pools for node %s: %s", node, e)
    return pools


def _parse_vm_disks(config: dict, kind: str) -> list[dict]:
    """Parse disk device entries from a VM/CT config — allocated size only."""
    disks = []
    prefixes = ("scsi", "virtio", "ide", "sata") if kind == "qemu" else ("rootfs", "mp")
    skip_keys = {"scsihw"} if kind == "qemu" else set()

    for key in config:
        if key in skip_keys:
            continue
        if not key.startswith(prefixes):
            continue
        value = config[key]
        if not isinstance(value, str):
            continue
        if "media=cdrom" in value or value == "none":
            continue

        parts    = value.split(",")
        vol      = parts[0]
        size_str = next((p.split("=")[1] for p in parts if p.startswith("size=")), "N/A")
        storage  = vol.split(":")[0] if ":" in vol else "N/A"

        disks.append({
            "device":    key,
            "storage":   storage,
            "allocated": size_str,
            "volume":    vol,
        })
    return disks


# ── tool ───────────────────────────────────────────────────────────────────────

class ListDisksTool(BaseTool):

    @property
    def name(self) -> str:
        return "list_disks"

    @property
    def description(self) -> str:
        return (
            "List disk information for the Proxmox cluster. "
            "Shows storage pool totals per node. "
            "For each VM/container: disk devices with allocated size. "
            "For running QEMU VMs with the guest agent: real per-filesystem usage "
            "(used, free, total GB per mount point). "
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

            node_result["storage_pools"] = _storage_pools(self.proxmox, node)

            # QEMU VMs
            try:
                for vm in self.proxmox.nodes(node).qemu.get():
                    vid    = str(vm.get("vmid"))
                    status = vm.get("status")
                    if vmid_filter and vid != str(vmid_filter):
                        continue

                    config = self.proxmox.nodes(node).qemu(vid).config.get()
                    disks  = _parse_vm_disks(config, "qemu")

                    # Guest agent fsinfo only available on running VMs
                    filesystems = []
                    if status == "running":
                        filesystems = _guest_fsinfo(self.proxmox, node, vid)

                    node_result["vms"].append({
                        "type":        "qemu",
                        "vmid":        vid,
                        "name":        vm.get("name", f"vm-{vid}"),
                        "status":      status,
                        "disks":       disks,
                        "filesystems": filesystems,  # empty if stopped or no agent
                    })
            except Exception as e:
                logger.error("Failed to fetch QEMU VMs on node %s: %s", node, e)

            # LXC containers
            try:
                for ct in self.proxmox.nodes(node).lxc.get():
                    vid    = str(ct.get("vmid"))
                    status = ct.get("status")
                    if vmid_filter and vid != str(vmid_filter):
                        continue

                    config = self.proxmox.nodes(node).lxc(vid).config.get()
                    disks  = _parse_vm_disks(config, "lxc")

                    node_result["vms"].append({
                        "type":        "lxc",
                        "vmid":        vid,
                        "name":        ct.get("name", f"ct-{vid}"),
                        "status":      status,
                        "disks":       disks,
                        "filesystems": [],  # LXC: no guest agent
                    })
            except Exception as e:
                logger.error("Failed to fetch LXC containers on node %s: %s", node, e)

            result[node] = node_result

        return json.dumps(result, indent=2)

    def as_fastmcp_fn(self):
        tool_self = self

        async def list_disks(vmid: str = "") -> str:
            """
            List disk information for the Proxmox cluster.
            Shows storage pool totals, disk devices with allocated size,
            and real filesystem usage per mount point for running VMs with guest agent.
            Optionally pass a vmid to filter to a single VM or container.
            """
            args = {}
            if vmid:
                args["vmid"] = vmid
            return await tool_self.run(args)

        return list_disks