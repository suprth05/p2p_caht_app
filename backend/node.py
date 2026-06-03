import uuid
import socket


class Node:
    def __init__(self, port=5000):
        self.node_id = str(uuid.uuid4())
        self.port = port
        self.ip = self._get_local_ip()
        print(f"Node started: {self.node_id} {self.ip}:{self.port}")

    def _get_local_ip(self):
        """
        Multi-strategy IP detection.  Priority order:
        1.  Parse `ip route` to find the default-route interface, then grab
            its IPv4 address — this is the most reliable on Linux.
        2.  Dummy-socket connect to a public IP (doesn't send traffic).
        3.  Enumerate all interfaces and pick the first non-junk one.
        4.  Last resort: 127.0.0.1
        """
        import subprocess

        # ── Strategy 1: ip route default ──────────────────────────────────
        try:
            # e.g.  "default via 192.168.43.1 dev wlan0 ..."
            route = subprocess.check_output(
                ['ip', 'route', 'get', '1.1.1.1'],
                stderr=subprocess.DEVNULL
            ).decode()
            # output: "1.1.1.1 via 192.168.43.1 dev wlan0 src 192.168.43.100 uid ..."
            for token_idx, token in enumerate(route.split()):
                if token == 'src' and token_idx + 1 < len(route.split()):
                    ip = route.split()[token_idx + 1]
                    if self._is_valid_ip(ip):
                        print(f"[IP detect] Strategy 1 (ip route): {ip}")
                        return ip
        except Exception:
            pass

        # ── Strategy 2: dummy socket ──────────────────────────────────────
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # This does NOT send any traffic — just lets the OS choose the
            # outbound interface.
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if self._is_valid_ip(ip):
                print(f"[IP detect] Strategy 2 (socket): {ip}")
                return ip
        except Exception:
            pass

        # ── Strategy 3: enumerate interfaces ──────────────────────────────
        try:
            output = subprocess.check_output(
                ['ip', '-o', '-4', 'addr', 'show'],
                stderr=subprocess.DEVNULL
            ).decode()
            ignore = ('lo', 'docker', 'veth', 'br-', 'virbr',
                      'vmnet', 'vboxnet', 'tailscale', 'tun', 'tap', 'wg')
            for line in output.strip().split('\n'):
                parts = line.split()
                if len(parts) < 4:
                    continue
                iface = parts[1]
                ip = parts[3].split('/')[0]
                if iface.startswith(ignore):
                    continue
                if self._is_valid_ip(ip):
                    print(f"[IP detect] Strategy 3 (enumerate {iface}): {ip}")
                    return ip
        except Exception:
            pass

        print("[IP detect] All strategies failed — using 127.0.0.1")
        return "127.0.0.1"

    @staticmethod
    def _is_valid_ip(ip):
        """Return True if ip looks like a real LAN address (not loopback,
        link-local, or Docker-internal 172.17.x.x)."""
        if not ip:
            return False
        if ip.startswith('127.'):
            return False
        if ip.startswith('169.254.'):
            return False
        if ip.startswith('172.17.'):       # Docker default bridge
            return False
        return True

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port
        }
