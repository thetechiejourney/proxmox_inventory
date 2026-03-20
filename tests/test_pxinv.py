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


# ── CLI integration tests (mocked) ───────────────────────────────────────────

MOCK_RESOURCES = [
    {
        "vmid": 100,
        "name": "homeassistant",
        "node": "pve-01",
        "type": "vm",
        "status": "running",
        "cpu_usage": 5.2,
        "mem_used": 1024**3,
        "mem_total": 4 * 1024**3,
        "disk_used": 10 * 1024**3,
        "disk_total": 32 * 1024**3,
        "uptime": 86400 * 3,
        "tags": "",
    },
    {
        "vmid": 101,
        "name": "pihole",
        "node": "pve-01",
        "type": "ct",
        "status": "running",
        "cpu_usage": 0.8,
        "mem_used": 128 * 1024**2,
        "mem_total": 512 * 1024**2,
        "disk_used": 1 * 1024**3,
        "disk_total": 8 * 1024**3,
        "uptime": 86400 * 14,
        "tags": "",
    },
    {
        "vmid": 200,
        "name": "talos-cp-01",
        "node": "pve-02",
        "type": "vm",
        "status": "stopped",
        "cpu_usage": 0,
        "mem_used": 0,
        "mem_total": 8 * 1024**3,
        "disk_used": 0,
        "disk_total": 64 * 1024**3,
        "uptime": 0,
        "tags": "",
    },
]

MOCK_NODES = [
    {
        "name": "pve-01",
        "status": "online",
        "cpu": 12.5,
        "mem_used": 8 * 1024**3,
        "mem_total": 32 * 1024**3,
        "uptime": 86400 * 30,
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


@patch("pxinv.cli.ProxmoxClient")
def test_list_table(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["list"])

    assert result.exit_code == 0
    # Rich may truncate long names in narrow terminals — check VMIDs which are always short
    assert "100" in result.output
    assert "101" in result.output
    assert "200" in result.output
    assert "running" in result.output
    assert "stopped" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_list_filter_status(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = [
        r for r in MOCK_RESOURCES if r["status"] == "running"
    ]
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["list", "--status", "running"])

    assert result.exit_code == 0
    mock_client.get_resources.assert_called_once_with(
        node=None, vm_type=None, status="running"
    )


@patch("pxinv.cli.ProxmoxClient")
def test_list_json_output(mock_cls):
    import json

    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["list", "--output", "json"])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert len(parsed) == 3
    assert parsed[0]["name"] == "homeassistant"


@patch("pxinv.cli.ProxmoxClient")
def test_summary(mock_cls):
    mock_client = MagicMock()
    mock_client.get_resources.return_value = MOCK_RESOURCES
    mock_client.get_nodes.return_value = MOCK_NODES
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["summary"])

    assert result.exit_code == 0
    assert "pve-01" in result.output
    assert "Cluster totals" in result.output


def test_list_missing_host():
    runner = _make_runner()
    result = runner.invoke(cli, ["--token-name", "t", "--token-value", "v", "list"])
    assert result.exit_code != 0


@patch("pxinv.cli.ProxmoxClient")
def test_start_running_vm(mock_cls):
    mock_client = MagicMock()
    mock_client.start_vm.side_effect = ValueError("homeassistant is already running")
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["start", "100"])

    assert result.exit_code != 0
    assert "already running" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_start_sends_task(mock_cls):
    mock_client = MagicMock()
    mock_client.start_vm.return_value = ("task-id-123", {"name": "talos-cp-01", "vmid": 200})
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["start", "200"])

    assert result.exit_code == 0
    assert "talos-cp-01" in result.output
    mock_client.start_vm.assert_called_once_with(200)


@patch("pxinv.cli.ProxmoxClient")
def test_stop_stopped_vm(mock_cls):
    mock_client = MagicMock()
    mock_client.stop_vm.side_effect = ValueError("talos-cp-01 is already stopped")
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["stop", "200"])

    assert result.exit_code != 0
    assert "already stopped" in result.output


@patch("pxinv.cli.ProxmoxClient")
def test_stop_sends_task(mock_cls):
    mock_client = MagicMock()
    mock_client.stop_vm.return_value = ("task-id-456", {"name": "homeassistant", "vmid": 100})
    mock_cls.return_value = mock_client

    runner = _make_runner()
    result = runner.invoke(cli, BASE_ARGS + ["stop", "100"])

    assert result.exit_code == 0
    assert "homeassistant" in result.output
    mock_client.stop_vm.assert_called_once_with(100)