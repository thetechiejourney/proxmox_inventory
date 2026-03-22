from proxmoxer import ProxmoxAPI
from proxmoxer.backends.https import AuthenticationError
from requests.exceptions import ConnectionError, SSLError


class PxinvConnectionError(Exception):
    pass


class PxinvAuthError(Exception):
    pass


class PxinvNotFoundError(Exception):
    pass


def _wrap_api_call(func):
    """Decorator that converts proxmoxer/requests exceptions into clean pxinv errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AuthenticationError:
            raise PxinvAuthError(
                "Authentication failed. Check your token name and token value."
            )
        except SSLError:
            raise PxinvConnectionError(
                "SSL verification failed. Use --no-verify-ssl if your Proxmox uses a self-signed certificate."
            )
        except ConnectionError as e:
            if "No route to host" in str(e) or "refused" in str(e).lower():
                raise PxinvConnectionError(
                    "Cannot connect to Proxmox. Check that the host is reachable and port 8006 is open."
                )
            raise PxinvConnectionError(f"Connection error: {e}")
    return wrapper


class ProxmoxClient:
    def __init__(self, host, user, token_name, token_value, verify_ssl=True):
        try:
            self._px = ProxmoxAPI(
                host,
                user=user,
                token_name=token_name,
                token_value=token_value,
                verify_ssl=verify_ssl,
            )
        except SSLError:
            raise PxinvConnectionError(
                "SSL verification failed. Use --no-verify-ssl if your Proxmox uses a self-signed certificate."
            )
        except ConnectionError as e:
            raise PxinvConnectionError(
                f"Cannot connect to {host}:8006 — {e}"
            )

    def _wait_task(self, node, task_id, timeout=60):
        """Poll a Proxmox task until it finishes. Raises ValueError if it fails."""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self._px.nodes(node).tasks(task_id).status.get()
            if status.get("status") == "stopped":
                if status.get("exitstatus") == "OK":
                    return
                raise ValueError(status.get("exitstatus", "Task failed"))
            time.sleep(1)
        raise ValueError(f"Task timed out after {timeout}s")

    @_wrap_api_call
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

    @_wrap_api_call
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

    @_wrap_api_call
    def start_vm(self, vmid):
        """Start a VM or container."""
        vm = self.get_vm(vmid)
        if not vm:
            raise PxinvNotFoundError(f"VMID {vmid} not found")
        if vm["status"] == "running":
            raise ValueError(f"{vm['name']} is already running")
        node = self._px.nodes(vm["node"])
        if vm["type"] == "qemu":
            return node.qemu(vmid).status.start.post(), vm
        return node.lxc(vmid).status.start.post(), vm

    @_wrap_api_call
    def stop_vm(self, vmid):
        """Gracefully shutdown a VM or container."""
        vm = self.get_vm(vmid)
        if not vm:
            raise PxinvNotFoundError(f"VMID {vmid} not found")
        if vm["status"] == "stopped":
            raise ValueError(f"{vm['name']} is already stopped")
        node = self._px.nodes(vm["node"])
        if vm["type"] == "qemu":
            return node.qemu(vmid).status.shutdown.post(), vm
        return node.lxc(vmid).status.shutdown.post(), vm

    @_wrap_api_call
    def get_vm_status(self, vmid):
        """Return current status of a VM/CT."""
        vm = self.get_vm(vmid)
        return vm["status"] if vm else None

    @_wrap_api_call
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

    @_wrap_api_call
    def get_vm_ip(self, vmid, node, vm_type):
        """Try to get the primary IP of a running VM via QEMU guest agent.
        Returns None if the agent is not available or the VM is stopped.
        Only works for VMs (qemu), not containers (lxc).
        """
        if vm_type != "vm":
            return None
        try:
            ifaces = self._px.nodes(node).qemu(vmid).agent("network-get-interfaces").get()
            for iface in ifaces.get("result", []):
                if iface.get("name") == "lo":
                    continue
                for addr in iface.get("ip-addresses", []):
                    if addr.get("ip-address-type") == "ipv4":
                        return addr["ip-address"]
        except Exception:
            return None
        return None

    @_wrap_api_call
    def restart_vm(self, vmid):
        """Gracefully restart a VM or container (shutdown + start)."""
        vm = self.get_vm(vmid)
        if not vm:
            raise PxinvNotFoundError(f"VMID {vmid} not found")
        if vm["status"] == "stopped":
            raise ValueError(f"{vm['name']} is stopped — use 'pxinv start' instead")
        node = self._px.nodes(vm["node"])
        if vm["type"] == "qemu":
            return node.qemu(vmid).status.reboot.post(), vm
        return node.lxc(vmid).status.reboot.post(), vm

    @_wrap_api_call
    def get_snapshots(self, vmid, node, vm_type):
        """Return list of snapshots for a VM or container."""
        node_api = self._px.nodes(node)
        if vm_type == "qemu":
            snaps = node_api.qemu(vmid).snapshot.get()
        else:
            snaps = node_api.lxc(vmid).snapshot.get()
        return [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "snaptime": s.get("snaptime", 0),
                "vmstate": s.get("vmstate", 0),
            }
            for s in snaps
            if s["name"] != "current"
        ]

    @_wrap_api_call
    def create_snapshot(self, vmid, name, description="", include_ram=False):
        """Create a snapshot of a VM or container. Waits for the task to complete."""
        vm = self.get_vm(vmid)
        if not vm:
            raise PxinvNotFoundError(f"VMID {vmid} not found")
        node_api = self._px.nodes(vm["node"])
        params = {"snapname": name, "description": description}
        if include_ram and vm["type"] == "qemu":
            params["vmstate"] = 1
        if vm["type"] == "qemu":
            task_id = node_api.qemu(vmid).snapshot.post(**params)
        else:
            task_id = node_api.lxc(vmid).snapshot.post(**params)
        self._wait_task(vm["node"], task_id)
        return task_id, vm

    @_wrap_api_call
    def delete_snapshot(self, vmid, name):
        """Delete a snapshot of a VM or container. Waits for the task to complete."""
        vm = self.get_vm(vmid)
        if not vm:
            raise PxinvNotFoundError(f"VMID {vmid} not found")
        node_api = self._px.nodes(vm["node"])
        if vm["type"] == "qemu":
            task_id = node_api.qemu(vmid).snapshot(name).delete()
        else:
            task_id = node_api.lxc(vmid).snapshot(name).delete()
        self._wait_task(vm["node"], task_id)
        return task_id, vm