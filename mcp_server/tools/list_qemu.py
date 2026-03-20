import json
import logging
from typing import Any
from .base import BaseTool

logger = logging.getLogger(__name__)


def _check_agent(proxmox, node: str, vmid: str) -> dict:
    """
    Probe the QEMU guest agent by calling the lightweight 'ping' command.
    Returns a status dict with installed/running/version info.
    """
    # First check if agent is enabled in VM config
    try:
        config = proxmox.nodes(node).qemu(vmid).config.get()
        agent_config = config.get("agent", "")
        enabled_in_config = "enabled=1" in str(agent_config) or agent_config == 1
    except Exception as e:
        logger.debug("qemu/%s: could not read config: %s", vmid, e)
        enabled_in_config = None

    # Ping the agent — fastest way to know if it's actually responding
    try:
        proxmox.nodes(node).qemu(vmid).agent("ping").post()
        agent_running = True
        logger.debug("qemu/%s: agent ping OK", vmid)
    except Exception as e:
        agent_running = False
        logger.debug("qemu/%s: agent ping failed: %s", vmid, e)

    # If agent is running, grab the version info
    agent_version = None
    guest_os = None
    if agent_running:
        try:
            info = proxmox.nodes(node).qemu(vmid).agent("info").get()
            result = info.get("result", {})
            agent_version = result.get("version")
            guest_os = result.get("supported-commands") and result.get("type")
        except Exception as e:
            logger.debug("qemu/%s: could not get agent info: %s", vmid, e)

        try:
            osinfo = proxmox.nodes(node).qemu(vmid).agent("get-osinfo").get()
            result = osinfo.get("result", {})
            guest_os = result.get("pretty-name") or result.get("name")
        except Exception as e:
            logger.debug("qemu/%s: could not get osinfo: %s", vmid, e)

    return {
        "enabled_in_config": enabled_in_config,
        "agent_running":     agent_running,
        "agent_version":     agent_version,
        "guest_os":          guest_os,
    }


class QemuAgentTool(BaseTool):

    @property
    def name(self) -> str:
        return "agent_status"

    @property
    def description(self) -> str:
        return (
            "Check the QEMU guest agent status for all (or one) QEMU VMs. "
            "Reports whether the agent is enabled in config, actually responding, "
            "its version, and the guest OS name. "
            "Useful to know which VMs support fsinfo, IP detection, etc."
        )

    async def run(self, arguments: dict[str, Any]) -> str:
        vmid_filter = arguments.get("vmid")
        results = []

        try:
            nodes = self.proxmox.nodes.get()
        except Exception as e:
            return f"Error: could not connect to Proxmox — {e}"

        for node_info in nodes:
            node = node_info["node"]
            try:
                vms = self.proxmox.nodes(node).qemu.get()
            except Exception as e:
                logger.error("Failed to list VMs on node %s: %s", node, e)
                continue

            for vm in vms:
                vid    = str(vm.get("vmid"))
                status = vm.get("status")

                if vmid_filter and vid != str(vmid_filter):
                    continue

                entry = {
                    "vmid":   vid,
                    "name":   vm.get("name", f"vm-{vid}"),
                    "node":   node,
                    "status": status,
                }

                if status != "running":
                    entry.update({
                        "enabled_in_config": None,
                        "agent_running":     False,
                        "agent_version":     None,
                        "guest_os":          None,
                        "note":              "VM is not running — cannot probe agent",
                    })
                else:
                    entry.update(_check_agent(self.proxmox, node, vid))

                logger.info("qemu/%s (%s): agent_running=%s", vid, entry["name"], entry.get("agent_running"))
                results.append(entry)

        if not results:
            return "No QEMU VMs found."

        return json.dumps(results, indent=2)

    def as_fastmcp_fn(self):
        tool_self = self

        async def agent_status(vmid: str = "") -> str:
            """
            Check the QEMU guest agent status for all VMs (or a specific one).
            Reports whether the agent is enabled, responding, its version, and guest OS.
            Pass a vmid to check a single VM.
            """
            args = {}
            if vmid:
                args["vmid"] = vmid
            return await tool_self.run(args)

        return agent_status