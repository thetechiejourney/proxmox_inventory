from proxmoxer import ProxmoxAPI


class ProxmoxClient:
    def __init__(self, host, user, token_name, token_value, verify_ssl=True):
        self._px = ProxmoxAPI(
            host,
            user=user,
            token_name=token_name,
            token_value=token_value,
            verify_ssl=verify_ssl,
        )

    def get_nodes(self):
        """Return list of nodes with basic stats."""
        nodes = []
        for node in self._px.nodes.get():
            nodes.append(
                {
                    "name": node["node"],
                    "status": node.get("status", "unknown"),
                    "cpu": round(node.get("cpu", 0) * 100, 1),
                    "mem_used": node.get("mem", 0),
                    "mem_total": node.get("maxmem", 0),
                    "uptime": node.get("uptime", 0),
                }
            )
        return nodes

    def get_resources(self, node=None, vm_type=None, status=None):
        """Return VMs and containers, optionally filtered."""
        resources = []

        for item in self._px.cluster.resources.get(type="vm"):
            vm_type_raw = item.get("type", "")  # "qemu" or "lxc"
            inferred_type = "vm" if vm_type_raw == "qemu" else "ct"

            if vm_type and vm_type != inferred_type:
                continue
            if node and item.get("node") != node:
                continue
            if status and item.get("status") != status:
                continue

            resources.append(
                {
                    "vmid": item.get("vmid"),
                    "name": item.get("name", f"vm-{item.get('vmid')}"),
                    "node": item.get("node"),
                    "type": inferred_type,
                    "status": item.get("status", "unknown"),
                    "cpu_usage": round(item.get("cpu", 0) * 100, 1),
                    "mem_used": item.get("mem", 0),
                    "mem_total": item.get("maxmem", 0),
                    "disk_used": item.get("disk", 0),
                    "disk_total": item.get("maxdisk", 0),
                    "uptime": item.get("uptime", 0),
                    "tags": item.get("tags", ""),
                }
            )

        return sorted(resources, key=lambda r: r["vmid"])