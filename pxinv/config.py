import os
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