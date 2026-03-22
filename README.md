# pxinv

A fast CLI for inventorying and managing VMs and containers on your Proxmox homelab.

![pxinv demo](assets/demo.gif)

## Installation

```bash
pip install pxinv
```

## Quick start

```bash
# Single host
export PXINV_HOST=192.168.1.10
export PXINV_TOKEN_NAME=pxinv
export PXINV_TOKEN_VALUE=<secret>
export PXINV_VERIFY_SSL=false

pxinv list
pxinv summary
pxinv watch
```

For persistent config, create `~/.config/pxinv/config.yaml`:

```yaml
# Single host
host: 192.168.1.10
user: root@pam
token_name: pxinv
token_value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
verify_ssl: false
```

```yaml
# Multiple clusters
clusters:
  home:
    host: 192.168.1.10
    token_name: pxinv
    token_value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    verify_ssl: false
  vps:
    host: 95.216.x.x
    token_name: pxinv
    token_value: yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

## Commands

| Command | Description |
|---|---|
| `pxinv list` | List all VMs and containers |
| `pxinv watch` | Live-refresh list (press Ctrl+C to exit) |
| `pxinv summary` | Cluster resource totals and node status |
| `pxinv start <vmid>` | Start a VM or container |
| `pxinv stop <vmid>` | Gracefully shut down a VM or container |
| `pxinv restart <vmid>` | Reboot a VM or container |
| `pxinv snapshots <vmid>` | List snapshots of a VM or container |
| `pxinv snapshot create <vmid> <name>` | Create a snapshot |
| `pxinv snapshot delete <vmid> <name>` | Delete a snapshot |
| `pxinv ansible-inventory` | Export Ansible dynamic inventory JSON |
| `pxinv clusters` | List configured clusters |

Use `pxinv <command> --help` for full options on any command.

## Key features

**Filtering** — `pxinv list` and `pxinv watch` support `--node`, `--type`, `--status`, and `--tags`. Tag matching is case-insensitive and supports multiple tags per VM.

**Output formats** — `pxinv list`, `pxinv summary`, and `pxinv snapshots` support `--output table/json/yaml`.

**Multi-cluster** — define multiple Proxmox hosts in your config and switch between them with `--cluster <name>`. When multiple clusters are active, a `CLUSTER` column appears automatically.

**Ansible integration** — `pxinv ansible-inventory` groups hosts by status, tag, and cluster. Add `--with-ips` to fetch IPs via QEMU guest agent.

**Self-signed certs** — use `--no-verify-ssl` or `PXINV_VERIFY_SSL=false`.

## Authentication

`pxinv` uses Proxmox API tokens. To create one: Datacenter → Permissions → API Tokens → Add. Required permissions: `VM.Audit` and `Sys.Audit` on `/`.

## Contributing

```bash
git clone https://github.com/thetechiejourney/pxinv
cd pxinv
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```