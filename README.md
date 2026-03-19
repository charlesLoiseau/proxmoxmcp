# Proxmox MCP Server

Expose your Proxmox VE cluster to Claude as MCP tools.

## Project structure

```
proxmox-mcp/
├── main.py                        # Entry point
├── requirements.txt
└── proxmox_mcp/
    ├── config.py                  # Env-var config (edit once)
    ├── client.py                  # Proxmox API client factory
    ├── server.py                  # MCP wiring (never needs to change)
    └── tools/
        ├── __init__.py            # ← Register new tools here
        ├── base.py                # BaseTool ABC
        └── list_vms.py            # Tool: list VMs & containers
```

### Adding a new tool

1. Create `proxmox_mcp/tools/your_tool.py` — subclass `BaseTool`, implement `name`, `description`, `input_schema`, and `run`.
2. Open `proxmox_mcp/tools/__init__.py` and append `YourTool` to `_TOOL_CLASSES`.

Done. The server picks it up automatically.

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
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

### 3. Environment variables

| Variable | Required | Description |
|---|---|---|
| `PROXMOX_HOST` | ✅ | IP or hostname |
| `PROXMOX_USER` | ✅ | e.g. `root@pam` |
| `PROXMOX_TOKEN_NAME` | ✅* | Token ID (e.g. `mcp`) |
| `PROXMOX_TOKEN_VALUE` | ✅* | Token secret |
| `PROXMOX_PASSWORD` | alt | Password auth (less secure) |
| `PROXMOX_PORT` | optional | Default `8006` |
| `PROXMOX_VERIFY_SSL` | optional | `true`/`false` (default `false`) |

---

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

> **IP addresses for QEMU VMs** require the QEMU guest agent to be running inside the VM (`apt install qemu-guest-agent`). LXC containers don't need it.
