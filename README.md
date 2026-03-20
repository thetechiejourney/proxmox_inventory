# pxinv

[![CI](https://github.com/yourusername/pxinv/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/pxinv/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pxinv)](https://pypi.org/project/pxinv/)
[![Python](https://img.shields.io/pypi/pyversions/pxinv)](https://pypi.org/project/pxinv/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A fast CLI for inventorying and managing VMs and containers on your Proxmox homelab.

```
$ pxinv list

 VMID  NAME             NODE    TYPE  STATUS   CPU    RAM              DISK             UPTIME  TAGS
──────────────────────────────────────────────────────────────────────────────────────────────────────
 100   homeassistant    pve-01  VM    running  5.2%   1.0GB/4.0GB      10.0GB/32.0GB    3d      homelab
 101   pihole           pve-01  CT    running  0.8%   128.0MB/512.0MB  1.0GB/8.0GB      14d     dns
 200   talos-cp-01      pve-02  VM    stopped  —      —/8.0GB          —/64.0GB         —       k8s

3 resource(s) — 2 running, 1 stopped
```

## Installation

```bash
pip install pxinv
```

Or install from source:

```bash
git clone https://github.com/yourusername/pxinv
cd pxinv
pip install -e .
```

## Authentication

`pxinv` uses Proxmox API tokens (recommended over username/password).

**Create a token in Proxmox:**
1. Go to Datacenter → Permissions → API Tokens
2. Add a token for your user (e.g. `root@pam`, token name: `pxinv`)
3. Copy the token value — it's only shown once

**Required permissions:** `VM.Audit` and `Sys.Audit` on `/` (or per-node).

## Configuration

Credentials can be provided in three ways (in order of precedence):

### 1. CLI flags
```bash
pxinv --host 192.168.1.10 --token-name pxinv --token-value <secret> list
```

### 2. Environment variables
```bash
export PXINV_HOST=192.168.1.10
export PXINV_TOKEN_NAME=pxinv
export PXINV_TOKEN_VALUE=<secret>
export PXINV_VERIFY_SSL=false   # optional, for self-signed certs

pxinv list
```

### 3. Config file

`~/.config/pxinv/config.yaml`:
```yaml
host: 192.168.1.10
user: root@pam
token_name: pxinv
token_value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
verify_ssl: false
```

## Commands

### `pxinv list`

List all VMs and containers.

```bash
# All guests
pxinv list

# Filter by node
pxinv list --node pve-01

# Only running containers
pxinv list --type ct --status running

# Filter by tag
pxinv list --tags k8s
pxinv list --tags homelab --status running

# JSON output (pipe to jq, etc.)
pxinv list --output json | jq '.[] | select(.cpu_usage > 50)'

# YAML output
pxinv list --output yaml
```

### `pxinv watch`

Live-refresh the VM/container list directly in the terminal. No flickering — powered by `rich.Live`. Press `Ctrl+C` to exit.

```bash
# Refresh every 5 seconds (default)
pxinv watch

# Custom interval
pxinv watch --interval 10

# Combinable with all list filters
pxinv watch --status running
pxinv watch --tags k8s --interval 3
pxinv watch --node pve-01
```

The panel header shows the refresh interval and the timestamp of the last update.

### `pxinv summary`

Show cluster-wide resource totals and node status.

```bash
pxinv summary
pxinv summary --output json
```

### `pxinv start <vmid>`

Start a VM or container by VMID.

```bash
pxinv start 100

# Wait until the VM is fully running before returning
pxinv start 100 --wait

# Custom timeout (default: 60s)
pxinv start 100 --wait --timeout 120
```

### `pxinv stop <vmid>`

Gracefully shut down a VM or container by VMID.

```bash
pxinv stop 100

# Wait until the VM is fully stopped before returning
pxinv stop 100 --wait
```

## Tags

Proxmox supports tagging VMs and containers via the UI (VM → Options → Tags). `pxinv` shows tags as a column in `pxinv list` and lets you filter by them:

```bash
pxinv list --tags homelab
pxinv list --tags k8s --status running
```

Tag matching is case-insensitive. Multiple tags per VM are supported — filtering matches any VM that contains the specified tag.

## Self-signed certificates

If your Proxmox uses the default self-signed cert, disable verification:

```bash
pxinv --no-verify-ssl list
# or
export PXINV_VERIFY_SSL=false
```

## Contributing

PRs welcome. To set up a dev environment:

```bash
git clone https://github.com/yourusername/pxinv
cd pxinv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT