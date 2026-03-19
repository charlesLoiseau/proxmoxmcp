from proxmoxer import ProxmoxAPI
from .config import ProxmoxConfig


def get_client(cfg: ProxmoxConfig) -> ProxmoxAPI:
    """Return an authenticated ProxmoxAPI instance."""
    if cfg.token_name and cfg.token_value:
        return ProxmoxAPI(
            cfg.host,
            port=cfg.port,
            user=cfg.user,
            token_name=cfg.token_name,
            token_value=cfg.token_value,
            verify_ssl=cfg.verify_ssl,
        )
    return ProxmoxAPI(
        cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        verify_ssl=cfg.verify_ssl,
    )
