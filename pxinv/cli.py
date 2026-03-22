import time
import warnings

warnings.filterwarnings("ignore", module="urllib3")
warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

import click  # noqa: E402
from rich.console import Console  # noqa: E402

from .client import ProxmoxClient, PxinvAuthError, PxinvConnectionError, PxinvNotFoundError  # noqa: E402
from .config import load_config, get_clusters  # noqa: E402
from .output import print_summary, print_table, build_watch_panel  # noqa: E402


@click.group()
@click.version_option(package_name="pxinv")
@click.option("--host", envvar="PXINV_HOST", help="Proxmox host (e.g. 192.168.1.10)")
@click.option("--user", envvar="PXINV_USER", default="root@pam", show_default=True)
@click.option("--token-name", envvar="PXINV_TOKEN_NAME", help="API token name")
@click.option("--token-value", envvar="PXINV_TOKEN_VALUE", help="API token value")
@click.option("--config", "config_path", default=None, help="Path to config file")
@click.option("--verify-ssl/--no-verify-ssl", default=True, envvar="PXINV_VERIFY_SSL")
@click.option("--cluster", "-c", default=None, envvar="PXINV_CLUSTER",
              help="Cluster name from config (default: all clusters)")
@click.pass_context
def cli(ctx, host, user, token_name, token_value, config_path, verify_ssl, cluster):
    """pxinv — Proxmox VM & container inventory CLI."""
    ctx.ensure_object(dict)

    cfg = load_config(config_path)
    clusters = get_clusters(cfg)

    # CLI flags override everything — treat as single "default" cluster
    if host:
        clusters = {
            "default": {
                "host": host,
                "user": user,
                "token_name": token_name,
                "token_value": token_value,
                "verify_ssl": verify_ssl,
            }
        }
        cluster = "default"

    if not clusters:
        raise click.UsageError(
            "No Proxmox host configured. Use --host, PXINV_HOST, or a config file."
        )

    # Validate --cluster if specified
    if cluster and cluster != "all" and cluster not in clusters:
        available = ", ".join(clusters.keys())
        raise click.UsageError(
            f"Unknown cluster '{cluster}'. Available: {available}"
        )

    ctx.obj["clusters"] = clusters
    ctx.obj["cluster"] = cluster  # None means all
    ctx.obj["verify_ssl"] = verify_ssl


def _get_clients(ctx):
    """Return list of (cluster_name, ProxmoxClient) tuples based on --cluster flag."""
    clusters = ctx.obj["clusters"]
    selected = ctx.obj["cluster"]

    targets = (
        {selected: clusters[selected]} if selected and selected != "all"
        else clusters
    ).items()

    clients = []
    for name, cfg in targets:
        missing = [k for k in ("host", "token_name", "token_value") if not cfg.get(k)]
        if missing:
            raise click.UsageError(
                f"Cluster '{name}' is missing: {', '.join(missing)}"
            )
        try:
            client = ProxmoxClient(
                host=cfg["host"],
                user=cfg.get("user", "root@pam"),
                token_name=cfg["token_name"],
                token_value=cfg["token_value"],
                verify_ssl=cfg.get("verify_ssl", True),
            )
            clients.append((name, client))
        except (PxinvConnectionError, PxinvAuthError) as e:
            raise click.ClickException(f"[{name}] {e}")

    return clients


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
@click.pass_context
def clusters(ctx):
    """List configured clusters."""
    from rich.table import Table
    from rich import box
    from rich.console import Console as RichConsole

    all_clusters = ctx.obj["clusters"]
    console = RichConsole()

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    table.add_column("NAME")
    table.add_column("HOST")
    table.add_column("USER", style="dim")

    for name, cfg in all_clusters.items():
        table.add_row(name, cfg.get("host", "—"), cfg.get("user", "root@pam"))

    console.print(table)


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
@click.option("--tags", default=None, help="Filter by tag (e.g. --tags homelab)")
@click.pass_context
def list(ctx, node, vm_type, status, output, tags):
    """List all VMs and containers."""
    try:
        clients = _get_clients(ctx)
        all_resources = []
        for cluster_name, client in clients:
            resources = client.get_resources(node=node, vm_type=vm_type, status=status)
            # Tag each resource with its cluster name
            for r in resources:
                r["cluster"] = cluster_name
            all_resources.extend(resources)
    except (PxinvConnectionError, PxinvAuthError, PxinvNotFoundError) as e:
        _catch(e)

    if tags:
        all_resources = [
            r for r in all_resources
            if tags.lower() in [t.strip().lower() for t in r.get("tags", "").split(";") if t.strip()]
        ]

    if output == "table":
        print_table(all_resources, show_cluster=len(clients) > 1)
    elif output == "json":
        import json
        click.echo(json.dumps(all_resources, indent=2))
    elif output == "yaml":
        import yaml
        click.echo(yaml.dump(all_resources, default_flow_style=False))


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
        clients = _get_clients(ctx)
        all_resources = []
        all_nodes = []
        for _, client in clients:
            all_resources.extend(client.get_resources())
            all_nodes.extend(client.get_nodes())
    except (PxinvConnectionError, PxinvAuthError) as e:
        _catch(e)

    if output == "table":
        print_summary(all_resources, all_nodes)
    elif output == "json":
        import json
        click.echo(json.dumps({"resources": all_resources, "nodes": all_nodes}, indent=2))
    elif output == "yaml":
        import yaml
        click.echo(yaml.dump({"resources": all_resources, "nodes": all_nodes}, default_flow_style=False))


@cli.command()
@click.option("--interval", "-i", default=5, show_default=True, help="Refresh interval in seconds")
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
@click.option("--tags", default=None, help="Filter by tag")
@click.pass_context
def watch(ctx, interval, node, vm_type, status, tags):
    """Live-refresh the VM/container list. Press Ctrl+C to exit."""
    from rich.live import Live
    clients = _get_clients(ctx)
    show_cluster = len(clients) > 1

    def fetch():
        try:
            all_resources = []
            for cluster_name, client in clients:
                resources = client.get_resources(node=node, vm_type=vm_type, status=status)
                for r in resources:
                    r["cluster"] = cluster_name
                all_resources.extend(resources)
            if tags:
                all_resources = [
                    r for r in all_resources
                    if tags.lower() in [t.strip().lower() for t in r.get("tags", "").split(";") if t.strip()]
                ]
            return all_resources
        except (PxinvConnectionError, PxinvAuthError) as e:
            raise click.ClickException(str(e))

    resources = fetch()
    try:
        with Live(build_watch_panel(resources, interval, show_cluster=show_cluster),
                  refresh_per_second=1, screen=True) as live:
            while True:
                time.sleep(interval)
                resources = fetch()
                live.update(build_watch_panel(resources, interval, show_cluster=show_cluster))
    except KeyboardInterrupt:
        pass


@cli.command()
@click.argument("vmid", type=int)
@click.option("--wait", is_flag=True, default=False, help="Wait until VM is running")
@click.option("--timeout", default=60, show_default=True, help="Timeout in seconds when using --wait")
@click.pass_context
def start(ctx, vmid, wait, timeout):
    """Start a VM or container by VMID."""
    client = _get_clients(ctx)[0][1]
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
    client = _get_clients(ctx)[0][1]
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


@cli.command()
@click.argument("vmid", type=int)
@click.option("--wait", is_flag=True, default=False, help="Wait until VM is running again")
@click.option("--timeout", default=120, show_default=True, help="Timeout in seconds when using --wait")
@click.pass_context
def restart(ctx, vmid, wait, timeout):
    """Reboot a VM or container by VMID."""
    client = _get_clients(ctx)[0][1]
    try:
        _, vm = client.restart_vm(vmid)
        click.echo(f"Restarting {vm['name']} ({vmid})...")
        if wait:
            _wait_for_status(client, vmid, "running", timeout)
            click.echo(f"{vm['name']} is running.")
        else:
            click.echo("Task sent. Use 'pxinv list' to check status.")
    except (PxinvConnectionError, PxinvAuthError, PxinvNotFoundError, ValueError) as e:
        if isinstance(e, ValueError):
            raise click.ClickException(str(e))
        _catch(e)



@cli.command("ansible-inventory")
@click.option("--with-ips", is_flag=True, default=False,
              help="Fetch IPs via QEMU guest agent (requires qemu-guest-agent installed in VMs)")
@click.option("--running-only", is_flag=True, default=False,
              help="Only include running VMs and containers")
@click.pass_context
def ansible_inventory(ctx, with_ips, running_only):
    """Export inventory in Ansible dynamic inventory JSON format."""
    import json

    clients = _get_clients(ctx)
    try:
        all_resources = []
        for cluster_name, client in clients:
            status_filter = "running" if running_only else None
            resources = client.get_resources(status=status_filter)
            for r in resources:
                r["cluster"] = cluster_name
                r["_client"] = client
            all_resources.extend(resources)
    except (PxinvConnectionError, PxinvAuthError) as e:
        _catch(e)

    hostvars = {}
    groups = {"all": {"hosts": [], "children": []}, "_meta": {"hostvars": {}}}
    status_groups = {}
    tag_groups = {}
    cluster_groups = {}

    for r in all_resources:
        hostname = r["name"]
        groups["all"]["hosts"].append(hostname)

        hvars = {
            "proxmox_vmid": r["vmid"],
            "proxmox_node": r["node"],
            "proxmox_type": r["type"],
            "proxmox_status": r["status"],
            "proxmox_cluster": r["cluster"],
            "proxmox_tags": [t.strip() for t in r.get("tags", "").split(";") if t.strip()],
        }

        if with_ips and r["status"] == "running":
            ip = r["_client"].get_vm_ip(r["vmid"], r["node"], r["type"])
            if ip:
                hvars["ansible_host"] = ip

        hostvars[hostname] = hvars

        status_groups.setdefault(r["status"], []).append(hostname)
        cluster_groups.setdefault(r["cluster"], []).append(hostname)
        for tag in hvars["proxmox_tags"]:
            tag_groups.setdefault(tag, []).append(hostname)

    for s, hosts in status_groups.items():
        groups[s] = {"hosts": hosts}
        groups["all"]["children"].append(s)

    for cluster_name, hosts in cluster_groups.items():
        groups[f"cluster_{cluster_name}"] = {"hosts": hosts}
        groups["all"]["children"].append(f"cluster_{cluster_name}")

    for tag, hosts in tag_groups.items():
        groups[f"tag_{tag}"] = {"hosts": hosts}
        groups["all"]["children"].append(f"tag_{tag}")

    groups["_meta"]["hostvars"] = hostvars
    groups["all"]["children"] = sorted(set(groups["all"]["children"]))

    click.echo(json.dumps(groups, indent=2))


def main():
    cli()