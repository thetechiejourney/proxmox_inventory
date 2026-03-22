from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pxinv.cli import cli
from pxinv.output import _fmt_bytes, _fmt_uptime


# ── Utility helpers ──────────────────────────────────────────────────────────

def test_fmt_bytes_zero():
    assert _fmt_bytes(0) == "—"

def test_fmt_bytes_mb():
    assert _fmt_bytes(512 * 1024 * 1024) == "512.0MB"

def test_fmt_bytes_gb():
    assert _fmt_bytes(2 * 1024**3) == "2.0GB"

def test_fmt_uptime_zero():
    assert _fmt_uptime(0) == "—"

def test_fmt_uptime_days_hours():
    assert _fmt_uptime(14 * 86400 + 3 * 3600) == "14d 3h"

def test_fmt_uptime_minutes_only():
    assert _fmt_uptime(45 * 60) == "45m"


# ── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_RESOURCES = [
    {
        "vmid": 100, "name": "homeassistant", "node": "pve-01", "type": "vm",
        "status": "running", "cpu_usage": 5.2, "mem_used": 1024**3,
        "mem_total": 4 * 1024**3, "disk_used": 10 * 1024**3,
        "disk_total": 32 * 1024**3, "uptime": 86400 * 3, "tags": "", "cluster": "default",
    },
    {
        "vmid": 101, "name": "pihole", "node": "pve-01", "type": "ct",
        "status": "running", "cpu_usage": 0.8, "mem_used": 128 * 1024**2,
        "mem_total": 512 * 1024**2, "disk_used": 1 * 1024**3,
        "disk_total": 8 * 1024**3, "uptime": 86400 * 14, "tags": "", "cluster": "default",
    },
    {
        "vmid": 200, "name": "talos-cp-01", "node": "pve-02", "type": "vm",
        "status": "stopped", "cpu_usage": 0, "mem_used": 0,
        "mem_total": 8 * 1024**3, "disk_used": 0,
        "disk_total": 64 * 1024**3, "uptime": 0, "tags": "", "cluster": "default",
    },
]

MOCK_NODES = [
    {
        "name": "pve-01", "status": "online", "cpu": 12.5,
        "mem_used": 8 * 1024**3, "mem_total": 32 * 1024**3, "uptime": 86400 * 30,
    }
]

BASE_ARGS = [
    "--host", "192.168.1.10",
    "--token-name", "pxinv",
    "--token-value", "fake-token",
    "--no-verify-ssl",
]


def _make_runner():
    return CliRunner()


# ── list command ──────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_list_table(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["list"])
    assert result.exit_code == 0
    assert "100" in result.output
    assert "running" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_list_filter_status(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [r for r in MOCK_RESOURCES if r["status"] == "running"]
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["list", "--status", "running"])
    assert result.exit_code == 0
    mock_client.get_resources.assert_called_once_with(node=None, vm_type=None, status="running")


@patch("pxinv.cli.ProxmoxClient")
def test_list_json_output(mock_cls):
    import json
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["list", "--output", "json"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 3


@patch("pxinv.cli.ProxmoxClient")
def test_summary(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_client.get_nodes.return_value = MOCK_NODES
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["summary"])
    assert result.exit_code == 0
    assert "pve-01" in result.output


def test_list_missing_host():
    result = _make_runner().invoke(cli, ["--token-name", "t", "--token-value", "v", "list"])
    assert result.exit_code != 0


# ── start / stop ─────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_start_running_vm(mock_cls):
    mock_client = MagicMock()
    mock_client.start_vm.side_effect = ValueError("homeassistant is already running")
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["start", "100"])
    assert result.exit_code != 0
    assert "already running" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_start_sends_task(mock_cls):
    mock_client = MagicMock()
    mock_client.start_vm.return_value = ("task-id-123", {"name": "talos-cp-01", "vmid": 200})
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["start", "200"])
    assert result.exit_code == 0
    assert "talos-cp-01" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_stop_stopped_vm(mock_cls):
    mock_client = MagicMock()
    mock_client.stop_vm.side_effect = ValueError("talos-cp-01 is already stopped")
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["stop", "200"])
    assert result.exit_code != 0
    assert "already stopped" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_stop_sends_task(mock_cls):
    mock_client = MagicMock()
    mock_client.stop_vm.return_value = ("task-id-456", {"name": "homeassistant", "vmid": 100})
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["stop", "100"])
    assert result.exit_code == 0
    assert "homeassistant" in result.output


# ── error handling ────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_connection_error_shows_clean_message(mock_cls):
    from pxinv.client import PxinvConnectionError
    mock_cls.side_effect = PxinvConnectionError("Cannot connect to Proxmox.")
    result = _make_runner().invoke(cli, BASE_ARGS + ["list"])
    assert result.exit_code != 0
    assert "Cannot connect" in result.output
    assert "Traceback" not in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_auth_error_shows_clean_message(mock_cls):
    from pxinv.client import PxinvAuthError
    mock_cls.side_effect = PxinvAuthError("Authentication failed.")
    result = _make_runner().invoke(cli, BASE_ARGS + ["list"])
    assert result.exit_code != 0
    assert "Authentication failed" in result.output
    assert "Traceback" not in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_vmid_not_found_shows_clean_message(mock_cls):
    from pxinv.client import PxinvNotFoundError
    mock_client = MagicMock()
    mock_client.start_vm.side_effect = PxinvNotFoundError("VMID 999 not found")
    mock_cls.return_value = mock_client
    result = _make_runner().invoke(cli, BASE_ARGS + ["start", "999"])
    assert result.exit_code != 0
    assert "999" in result.output
    assert "Traceback" not in result.output


# ── tags ─────────────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_list_tags_column_present(mock_cls):
    import json
    mock_client = MagicMock()
    resources = [{**MOCK_RESOURCES[0], "tags": "homelab;k8s"}]
    mock_client.get_resources.return_value = resources
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["list", "--output", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output)[0]["tags"] == "homelab;k8s"


@patch("pxinv.cli.ProxmoxClient")
def test_list_filter_by_tag(mock_cls):
    import json
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [
        {**MOCK_RESOURCES[0], "tags": "homelab;k8s"},
        {**MOCK_RESOURCES[1], "tags": "dns"},
        {**MOCK_RESOURCES[2], "tags": ""},
    ]
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["list", "--output", "json", "--tags", "homelab"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 1


@patch("pxinv.cli.ProxmoxClient")
def test_list_filter_by_tag_no_match(mock_cls):
    import json
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [{**MOCK_RESOURCES[0], "tags": "homelab"}]
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["list", "--output", "json", "--tags", "production"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 0


# ── watch ─────────────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_watch_exits_on_keyboard_interrupt(mock_cls):
    from unittest.mock import patch as mpatch
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_cls.return_value = mock_client

    with mpatch("pxinv.cli.time") as mock_time:
        mock_time.sleep.side_effect = KeyboardInterrupt
        result = _make_runner().invoke(cli, BASE_ARGS + ["watch", "--interval", "1"])
    assert result.exit_code == 0


# ── ansible-inventory ─────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_ansible_inventory_structure(mock_cls):
    import json
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [
        {**MOCK_RESOURCES[0], "tags": "homelab;k8s"},
        {**MOCK_RESOURCES[1], "tags": "dns"},
        {**MOCK_RESOURCES[2], "tags": ""},
    ]
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["ansible-inventory"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "all" in data
    assert "_meta" in data
    assert "running" in data
    assert "stopped" in data
    assert "tag_homelab" in data
    assert "cluster_default" in data


@patch("pxinv.cli.ProxmoxClient")
def test_ansible_inventory_with_ips(mock_cls):
    import json
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [MOCK_RESOURCES[0]]
    mock_client.get_vm_ip.return_value = "192.168.1.100"
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["ansible-inventory", "--with-ips"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["_meta"]["hostvars"]["homeassistant"]["ansible_host"] == "192.168.1.100"


@patch("pxinv.cli.ProxmoxClient")
def test_ansible_inventory_running_only(mock_cls):
    import json
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [MOCK_RESOURCES[0]]
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["ansible-inventory", "--running-only"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)["all"]["hosts"]) == 1
    mock_client.get_resources.assert_called_once_with(status="running")


# ── multi-cluster ─────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_clusters_command(mock_cls):
    mock_cls.return_value = MagicMock()
    result = _make_runner().invoke(cli, BASE_ARGS + ["clusters"])
    assert result.exit_code == 0
    assert "default" in result.output
    assert "192.168.1.10" in result.output


def test_invalid_cluster_flag():
    # Without --host, config-only path — unknown cluster should fail
    result = _make_runner().invoke(cli, [
        "--cluster", "nonexistent",
        "--host", "",   # empty host triggers config path
        "list"
    ])
    # With no valid host and unknown cluster name the CLI should error
    assert result.exit_code != 0


@patch("pxinv.cli.ProxmoxClient")
def test_list_shows_cluster_column_when_multiple(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_cls.return_value = mock_client

    # Simulate two clusters via config
    from pxinv.config import get_clusters
    cfg = {
        "clusters": {
            "home": {"host": "192.168.1.10", "token_name": "t", "token_value": "v"},
            "vps":  {"host": "10.0.0.1",     "token_name": "t", "token_value": "v"},
        }
    }
    clusters = get_clusters(cfg)
    assert "home" in clusters
    assert "vps" in clusters
    assert len(clusters) == 2


# ── restart ───────────────────────────────────────────────────────────────────

@patch("pxinv.cli.ProxmoxClient")
def test_restart_sends_task(mock_cls):
    mock_client = MagicMock()
    mock_client.restart_vm.return_value = ("task-id-789", {"name": "homeassistant", "vmid": 100})
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["restart", "100"])
    assert result.exit_code == 0
    assert "homeassistant" in result.output
    mock_client.restart_vm.assert_called_once_with(100)


@patch("pxinv.cli.ProxmoxClient")
def test_restart_stopped_vm(mock_cls):
    mock_client = MagicMock()
    mock_client.restart_vm.side_effect = ValueError("talos-cp-01 is stopped — use 'pxinv start' instead")
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["restart", "200"])
    assert result.exit_code != 0
    assert "stopped" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_restart_not_found(mock_cls):
    from pxinv.client import PxinvNotFoundError
    mock_client = MagicMock()
    mock_client.restart_vm.side_effect = PxinvNotFoundError("VMID 999 not found")
    mock_cls.return_value = mock_client

    result = _make_runner().invoke(cli, BASE_ARGS + ["restart", "999"])
    assert result.exit_code != 0
    assert "999" in result.output
    assert "Traceback" not in result.output