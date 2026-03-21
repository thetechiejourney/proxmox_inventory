# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-21

### Added
- `pxinv ansible-inventory` — export inventory in Ansible dynamic inventory JSON format, grouped by status and tag
- `--with-ips` flag to fetch VM IPs via QEMU guest agent
- `--running-only` flag to limit inventory to running guests

## [0.2.0] - 2026-03-21

### Added
- `pxinv watch` — live-refresh table using `rich.Live`, no flickering, press Ctrl+C to exit
- `pxinv list --tags` — filter VMs and containers by Proxmox tag
- TAGS column in `pxinv list` output
- `pxinv start <vmid>` — start a VM or container by VMID
- `pxinv stop <vmid>` — gracefully shut down a VM or container by VMID
- `--wait` and `--timeout` flags for `start` and `stop`
- Clean error messages for connection errors, auth failures, and missing VMIDs — no more tracebacks

### Changed
- `pxinv list --output csv` removed from docs (not yet implemented)

## [0.1.0] - 2026-03-21

### Added
- `pxinv list` — list all VMs and containers with VMID, name, node, type, status, CPU, RAM, disk, and uptime
- `pxinv summary` — cluster-wide resource totals and node status
- Filter by node (`--node`), type (`--type`), and status (`--status`)
- Output formats: table, JSON, YAML
- Config via CLI flags, environment variables, or `~/.config/pxinv/config.yaml`
- `--no-verify-ssl` support for self-signed Proxmox certificates
- GitHub Actions: CI (lint + test on Python 3.9/3.11/3.12), release to PyPI on tag, weekly dependency audit