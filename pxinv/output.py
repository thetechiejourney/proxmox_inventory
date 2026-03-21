from datetime import datetime

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _fmt_bytes(b):
    if b == 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}PB"


def _fmt_uptime(seconds):
    if not seconds:
        return "—"
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins and not days:
        parts.append(f"{mins}m")
    return " ".join(parts) or "< 1m"


def _status_style(status):
    return {
        "running": "[green]running[/green]",
        "stopped": "[red]stopped[/red]",
        "paused": "[yellow]paused[/yellow]",
    }.get(status, status)


def _type_style(t):
    return "[cyan]VM[/cyan]" if t == "vm" else "[magenta]CT[/magenta]"


def build_table(resources, show_cluster=False):
    """Build and return a Rich Table from a list of resources."""
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    if show_cluster:
        table.add_column("CLUSTER", style="dim")
    table.add_column("VMID", style="dim", width=6)
    table.add_column("NAME", min_width=20)
    table.add_column("NODE", style="dim")
    table.add_column("TYPE", width=4)
    table.add_column("STATUS", width=9)
    table.add_column("CPU", justify="right", width=6)
    table.add_column("RAM", justify="right", width=14)
    table.add_column("DISK", justify="right", width=14)
    table.add_column("UPTIME", justify="right", width=10)
    table.add_column("TAGS", style="dim")

    for r in resources:
        mem = f"{_fmt_bytes(r['mem_used'])}/{_fmt_bytes(r['mem_total'])}"
        disk = f"{_fmt_bytes(r['disk_used'])}/{_fmt_bytes(r['disk_total'])}"
        cpu = f"{r['cpu_usage']}%" if r["status"] == "running" else "—"
        tags = r.get("tags", "").replace(";", " ") if r.get("tags") else ""
        row = []
        if show_cluster:
            row.append(r.get("cluster", ""))
        row.extend([
            str(r["vmid"]),
            r["name"],
            r["node"],
            _type_style(r["type"]),
            _status_style(r["status"]),
            cpu,
            mem,
            disk,
            _fmt_uptime(r["uptime"]),
            tags,
        ])
        table.add_row(*row)

    return table


def build_footer(resources):
    """Return a footer Text with running/stopped counts."""
    running = sum(1 for r in resources if r["status"] == "running")
    stopped = sum(1 for r in resources if r["status"] == "stopped")
    return Text(
        f"{len(resources)} resource(s) — {running} running, {stopped} stopped",
        style="dim",
    )


def print_table(resources, show_cluster=False):
    if not resources:
        console.print("[yellow]No resources found.[/yellow]")
        return
    console.print(build_table(resources, show_cluster=show_cluster))
    console.print(build_footer(resources))


def build_watch_panel(resources, interval, show_cluster=False):
    """Build a Panel containing the table + footer for use with rich.Live."""
    if not resources:
        content = Text("No resources found.", style="yellow")
    else:
        from rich.console import Group
        content = Group(build_table(resources, show_cluster=show_cluster), build_footer(resources))

    timestamp = datetime.now().strftime("%H:%M:%S")
    return Panel(
        content,
        title="[bold]pxinv watch[/bold]",
        subtitle=f"[dim]refreshing every {interval}s — last update {timestamp} — press Ctrl+C to exit[/dim]",
        border_style="dim",
    )


def print_summary(resources, nodes):
    node_table = Table(
        title="Nodes", box=box.SIMPLE_HEAD, show_header=True, header_style="bold"
    )
    node_table.add_column("NODE")
    node_table.add_column("STATUS")
    node_table.add_column("CPU", justify="right")
    node_table.add_column("RAM", justify="right", width=16)
    node_table.add_column("UPTIME", justify="right")

    for n in nodes:
        mem = f"{_fmt_bytes(n['mem_used'])}/{_fmt_bytes(n['mem_total'])}"
        node_table.add_row(
            n["name"],
            _status_style(n["status"]),
            f"{n['cpu']}%",
            mem,
            _fmt_uptime(n["uptime"]),
        )

    console.print(node_table)

    total = len(resources)
    running = sum(1 for r in resources if r["status"] == "running")
    stopped = sum(1 for r in resources if r["status"] == "stopped")
    vms = sum(1 for r in resources if r["type"] == "vm")
    cts = sum(1 for r in resources if r["type"] == "ct")
    total_mem = sum(r["mem_total"] for r in resources)
    used_mem = sum(r["mem_used"] for r in resources)
    total_disk = sum(r["disk_total"] for r in resources if r["disk_total"] > 0)
    used_disk = sum(r["disk_used"] for r in resources if r["disk_total"] > 0)

    summary_table = Table(
        title="Cluster totals", box=box.SIMPLE_HEAD, header_style="bold"
    )
    summary_table.add_column("METRIC")
    summary_table.add_column("VALUE", justify="right")

    summary_table.add_row("Total guests", str(total))
    summary_table.add_row("  VMs", str(vms))
    summary_table.add_row("  Containers", str(cts))
    summary_table.add_row("Running", f"[green]{running}[/green]")
    summary_table.add_row("Stopped", f"[red]{stopped}[/red]")
    summary_table.add_row(
        "RAM allocated",
        f"{_fmt_bytes(used_mem)} / {_fmt_bytes(total_mem)}",
    )
    summary_table.add_row(
        "Disk allocated",
        f"{_fmt_bytes(used_disk)} / {_fmt_bytes(total_disk)}" if total_disk > 0 else "—  (no data)",
    )

    console.print(summary_table)