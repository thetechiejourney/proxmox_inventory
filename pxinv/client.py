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

    def get_vm(self, vmid):
        """Find a VM/CT by VMID and return its node and type."""
        for item in self._px.cluster.resources.get(type="vm"):
            if item.get("vmid") == vmid:
                return {
                    "vmid": vmid,
                    "node": item["node"],
                    "type": "qemu" if item["type"] == "qemu" else "lxc",
                    "status": item["status"],
                    "name": item.get("name", f"vm-{vmid}"),
                }
        return None

    def start_vm(self, vmid):
        """Start a VM or container."""
        vm = self.get_vm(vmid)
        if not vm:
            raise ValueError(f"VMID {vmid} not found")
        if vm["status"] == "running":
            raise ValueError(f"{vm['name']} is already running")
        node = self._px.nodes(vm["node"])
        if vm["type"] == "qemu":
            return node.qemu(vmid).status.start.post(), vm
        return node.lxc(vmid).status.start.post(), vm

    def stop_vm(self, vmid):
        """Gracefully shutdown a VM or container."""
        vm = self.get_vm(vmid)
        if not vm:
            raise ValueError(f"VMID {vmid} not found")
        if vm["status"] == "stopped":
            raise ValueError(f"{vm['name']} is already stopped")
        node = self._px.nodes(vm["node"])
        if vm["type"] == "qemu":
            return node.qemu(vmid).status.shutdown.post(), vm
        return node.lxc(vmid).status.shutdown.post(), vm

    def get_vm_status(self, vmid):
        """Return current status of a VM/CT."""
        vm = self.get_vm(vmid)
        return vm["status"] if vm else None

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

        return sorted(resources, key=lambda r: (r["node"], r["name"]))