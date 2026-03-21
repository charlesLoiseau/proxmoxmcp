# Proxmox MCP Server

Expose your Proxmox VE cluster to Claude as MCP tools.

## Setup

### 1. Install dependencies

```bash
uv run main.py
```

#### 1.1 Test the agent
```bash
uv run mcp dev main.py
```

### 2. Create a Proxmox API token (recommended)

In the Proxmox web UI:
1. **Datacenter → Permissions → API Tokens** → Add
2. User: `root@pam`, Token ID: `mcp`, uncheck *Privilege Separation*
3. Copy the secret shown (only displayed once)

Grant read access:
```
Datacenter → Permissions → Add → API Token Permission
  Path:  /
  Token: root@pam!mcp
  Role:  PVEAuditor
```

## Claude Desktop configuration

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
`%APPDATA%\Claude\claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "python3",
      "args": ["/absolute/path/to/proxmox-mcp/main.py"],
      "env": {
        "PROXMOX_HOST": "192.168.1.10",
        "PROXMOX_USER": "root@pam",
        "PROXMOX_TOKEN_NAME": "mcp",
        "PROXMOX_TOKEN_VALUE": "your-secret-token-value"
      }
    }
  }
}
```

---

## Available tools

| Tool | Description |
|---|---|
| `list_vms` | List all VMs/containers with CPU %, RAM, IP, uptime, I/O |
|`list_disk`| List storage pool information and disk usage on qemu vm with agent installed|
|`list_qemu`| get information on the qemu agent |

> **IP addresses for QEMU VMs** require the QEMU guest agent to be running inside the VM (`apt install qemu-guest-agent`). LXC containers don't need it.
> **Disk space** require QEMU guest agent to be running on the vm
