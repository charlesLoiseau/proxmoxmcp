import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# auto search for .env in case it is moved
_PROJECT_ROOT = Path(__file__).parent.parent
for _candidate in [
    Path.cwd() / ".env",
    _PROJECT_ROOT / ".env",
    Path(__file__).parent / ".env",
]:
    if _candidate.exists():
        load_dotenv(_candidate)
        break
 
@dataclass
class ProxmoxConfig:
    host: str
    user: str
    port: int
    verify_ssl: bool
    password: str
    token_name: str
    token_value: str
 
    def validate(self):
        if not self.host:
            raise ValueError("PROXMOX_HOST is not set.")
        has_token = self.token_name and self.token_value
        has_password = bool(self.password)
        if not has_token and not has_password:
            raise ValueError(
                "Set PROXMOX_PASSWORD, or both PROXMOX_TOKEN_NAME and PROXMOX_TOKEN_VALUE."
            )
 
 
def load_config() -> ProxmoxConfig:
    cfg = ProxmoxConfig(
        host=os.environ.get("PROXMOX_HOST", ""),
        user=os.environ.get("PROXMOX_USER", "root@pam"),
        port=int(os.environ.get("PROXMOX_PORT", "8006")),
        verify_ssl=os.environ.get("PROXMOX_VERIFY_SSL", "false").lower() == "true",
        password=os.environ.get("PROXMOX_PASSWORD", ""),
        token_name=os.environ.get("PROXMOX_TOKEN_NAME", ""),
        token_value=os.environ.get("PROXMOX_TOKEN_VALUE", ""),
    )
    cfg.validate()
    return cfg