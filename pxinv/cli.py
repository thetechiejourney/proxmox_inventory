import time
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

import click  # noqa: E402
from rich.console import Console  # noqa: E402

from .client import ProxmoxClient, PxinvAuthError, PxinvConnectionError, PxinvNotFoundError  # noqa: E402
from .config import load_config  # noqa: E402
from .output import print_summary, print_table  # noqa: E402


@click.group()
@click.version_option(version="0.1.0")
@click.option("--host", envvar="PXINV_HOST", help="Proxmox host (e.g. 192.168.1.10)")
@click.option("--user", envvar="PXINV_USER", default="root@pam", show_default=True)
@click.option("--token-name", envvar="PXINV_TOKEN_NAME", help="API token name")
@click.option("--token-value", envvar="PXINV_TOKEN_VALUE", help="API token value")
@click.option("--config", "config_path", default=None, help="Path to config file")
@click.option("--verify-ssl/--no-verify-ssl", default=True, envvar="PXINV_VERIFY_SSL")
@click.pass_context
def cli(ctx, host, user, token_name, token_value, config_path, verify_ssl):
    """pxinv — Proxmox VM & container inventory CLI."""
    ctx.ensure_object(dict)

    cfg = load_config(config_path)

    ctx.obj["host"] = host or cfg.get("host")
    ctx.obj["user"] = user or cfg.get("user", "root@pam")
    ctx.obj["token_name"] = token_name or cfg.get("token_name")
    ctx.obj["token_value"] = token_value or cfg.get("token_value")
    ctx.obj["verify_ssl"] = verify_ssl

    if not ctx.obj["host"]:
        raise click.UsageError(
            "Proxmox host is required. Use --host, PXINV_HOST env var, or config file."
        )


def _get_client(ctx):
    obj = ctx.obj
    missing = [k for k in ("host", "token_name", "token_value") if not obj.get(k)]
    if missing:
        raise click.UsageError(
            f"Missing required config: {', '.join(missing)}. "
            "Use CLI flags, env vars (PXINV_*), or a config file."
        )
    try:
        return ProxmoxClient(
            host=obj["host"],
            user=obj["user"],
            token_name=obj["token_name"],
            token_value=obj["token_value"],
            verify_ssl=obj["verify_ssl"],
        )
    except (PxinvConnectionError, PxinvAuthError) as e:
        raise click.ClickException(str(e))


def _catch(exc):
    """Re-raise pxinv domain errors as clean ClickExceptions."""
    if isinstance(exc, (PxinvConnectionError, PxinvAuthError, PxinvNotFoundError)):
        raise click.ClickException(str(exc))
    raise exc


def _wait_for_status(client, vmid, target_status, timeout):
    """Poll until VM reaches target_status or timeout."""
    console = Console()
    deadline = time.time() + timeout
    with console.status(f"Waiting for {target_status}..."):
        while time.time() < deadline:
            current = client.get_vm_status(vmid)
            if current == target_status:
                return
            time.sleep(2)
    raise click.ClickException(
        f"Timeout after {timeout}s — last status: {client.get_vm_status(vmid)}"
    )


@cli.command()
@click.option("--node", default=None, help="Filter by node name")
@click.option(
    "--type", "vm_type", default=None,
    type=click.Choice(["vm", "ct"]),
    help="Filter by type: vm or ct",
)
@click.option(
    "--status", default=None,
    type=click.Choice(["running", "stopped", "paused"]),
    help="Filter by status",
)
@click.option(
    "--output", "-o", default="table",
    type=click.Choice(["table", "json", "yaml"]),
    show_default=True, help="Output format",
)
@click.pass_context
def list(ctx, node, vm_type, status, output):
    """List all VMs and containers."""
    try:
        client = _get_client(ctx)
        resources = client.get_resources(node=node, vm_type=vm_type, status=status)
    except (PxinvConnectionError, PxinvAuthError, PxinvNotFoundError) as e:
        _catch(e)

    if output == "table":
        print_table(resources)
    elif output == "json":
        import json
        click.echo(json.dumps(resources, indent=2))
    elif output == "yaml":
        import yaml
        click.echo(yaml.dump(resources, default_flow_style=False))


@cli.command()
@click.option(
    "--output", "-o", default="table",
    type=click.Choice(["table", "json", "yaml"]),
    show_default=True,
)
@click.pass_context
def summary(ctx, output):
    """Show cluster resource summary."""
    try:
        client = _get_client(ctx)
        resources = client.get_resources()
        nodes = client.get_nodes()
    except (PxinvConnectionError, PxinvAuthError) as e:
        _catch(e)

    if output == "table":
        print_summary(resources, nodes)
    elif output == "json":
        import json
        click.echo(json.dumps({"resources": resources, "nodes": nodes}, indent=2))
    elif output == "yaml":
        import yaml
        click.echo(yaml.dump({"resources": resources, "nodes": nodes}, default_flow_style=False))


@cli.command()
@click.argument("vmid", type=int)
@click.option("--wait", is_flag=True, default=False, help="Wait until VM is running")
@click.option("--timeout", default=60, show_default=True, help="Timeout in seconds when using --wait")
@click.pass_context
def start(ctx, vmid, wait, timeout):
    """Start a VM or container by VMID."""
    client = _get_client(ctx)
    try:
        _, vm = client.start_vm(vmid)
        click.echo(f"Starting {vm['name']} ({vmid})...")
        if wait:
            _wait_for_status(client, vmid, "running", timeout)
            click.echo(f"{vm['name']} is running.")
        else:
            click.echo("Task sent. Use 'pxinv list' to check status.")
    except (PxinvConnectionError, PxinvAuthError, PxinvNotFoundError, ValueError) as e:
        if isinstance(e, ValueError):
            raise click.ClickException(str(e))
        _catch(e)


@cli.command()
@click.argument("vmid", type=int)
@click.option("--wait", is_flag=True, default=False, help="Wait until VM is stopped")
@click.option("--timeout", default=60, show_default=True, help="Timeout in seconds when using --wait")
@click.pass_context
def stop(ctx, vmid, wait, timeout):
    """Gracefully shut down a VM or container by VMID."""
    client = _get_client(ctx)
    try:
        _, vm = client.stop_vm(vmid)
        click.echo(f"Stopping {vm['name']} ({vmid})...")
        if wait:
            _wait_for_status(client, vmid, "stopped", timeout)
            click.echo(f"{vm['name']} is stopped.")
        else:
            click.echo("Task sent. Use 'pxinv list' to check status.")
    except (PxinvConnectionError, PxinvAuthError, PxinvNotFoundError, ValueError) as e:
        if isinstance(e, ValueError):
            raise click.ClickException(str(e))
        _catch(e)


def main():
    cli()