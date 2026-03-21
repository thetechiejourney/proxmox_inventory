from pathlib import Path

import yaml


DEFAULT_CONFIG_PATHS = [
    Path.home() / ".config" / "pxinv" / "config.yaml",
    Path.home() / ".pxinv.yaml",
    Path("pxinv.yaml"),
]


def load_config(path=None):
    """Load config from file. Returns empty dict if not found."""
    candidates = [Path(path)] if path else DEFAULT_CONFIG_PATHS

    for candidate in candidates:
        if candidate.exists():
            with open(candidate) as f:
                return yaml.safe_load(f) or {}

    return {}


def get_clusters(cfg):
    """Extract clusters from config.

    Supports two formats:
      - Legacy: flat config with host/token_name/token_value at root
      - Multi-cluster: clusters dict with named entries

    Returns a dict of {cluster_name: {host, user, token_name, token_value, verify_ssl}}
    """
    if "clusters" in cfg:
        clusters = {}
        for name, entry in cfg["clusters"].items():
            clusters[name] = {
                "host": entry.get("host"),
                "user": entry.get("user", "root@pam"),
                "token_name": entry.get("token_name"),
                "token_value": entry.get("token_value"),
                "verify_ssl": entry.get("verify_ssl", True),
            }
        return clusters

    # Legacy single-host format — expose as "default" cluster
    if cfg.get("host"):
        return {
            "default": {
                "host": cfg.get("host"),
                "user": cfg.get("user", "root@pam"),
                "token_name": cfg.get("token_name"),
                "token_value": cfg.get("token_value"),
                "verify_ssl": cfg.get("verify_ssl", True),
            }
        }

    return {}