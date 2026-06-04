import uuid
import socket
import subprocess


# Interfaces that are NEVER real physical network adapters
_VIRTUAL_IFACES = ('lo', 'docker', 'veth', 'br-', 'virbr',
                   'vmnet', 'vboxnet', 'tailscale', 'tun', 'tap', 'wg')

# Interfaces that are WiFi (prioritise these for hotspot use)
_WIFI_PREFIXES = ('wlan', 'wlp', 'wlo')


class Node:
    def __init__(self, port=5000, ip_override=None):
        self.node_id = str(uuid.uuid4())
        self.port = port

        if ip_override:
            self.ip = ip_override
        else:
            self.ip = self._get_local_ip()

        print(f"Node started: {self.node_id} {self.ip}:{self.port}")

    # ------------------------------------------------------------------
    def _get_local_ip(self):
        """
        Detect the real LAN IP fully automatically.

        Strategy:
          1.  Parse `ip -o -4 addr show` to get every (interface, ip) pair.
          2.  Throw away virtual / container interfaces by NAME.
          3.  Only reject 127.x.x.x and 169.254.x.x (link-local) by IP.
              Do NOT reject 172.x.x.x — real networks use that range.
          4.  Prefer WiFi interfaces (wlan/wlp) because the user is on a
              mobile hotspot.
          5.  Fallback: `hostname -I`, then dummy-socket.
        """

        # ── Primary: enumerate interfaces ─────────────────────────────
        wifi_ips = []
        other_ips = []

        try:
            out = subprocess.check_output(
                ['ip', '-o', '-4', 'addr', 'show'],
                stderr=subprocess.DEVNULL
            ).decode()

            for line in out.strip().split('\n'):
                parts = line.split()
                if len(parts) < 4:
                    continue

                iface = parts[1]
                ip = parts[3].split('/')[0]

                # Skip virtual interfaces
                if iface.startswith(_VIRTUAL_IFACES):
                    continue

                # Skip obviously unusable IPs
                if ip.startswith('127.') or ip.startswith('169.254.'):
                    continue

                if iface.startswith(_WIFI_PREFIXES):
                    wifi_ips.append((iface, ip))
                else:
                    other_ips.append((iface, ip))

        except Exception:
            pass

        # Prefer WiFi (hotspot), then wired
        all_ips = wifi_ips + other_ips

        if all_ips:
            iface, ip = all_ips[0]
            print(f"[IP] Detected {ip} on {iface}  "
                  f"(all: {[(i,a) for i,a in all_ips]})")
            return ip

        # ── Fallback 1: hostname -I ───────────────────────────────────
        try:
            out = subprocess.check_output(
                ['hostname', '-I'], stderr=subprocess.DEVNULL
            ).decode().strip()
            for ip in out.split():
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    print(f"[IP] Detected {ip} via hostname -I")
                    return ip
        except Exception:
            pass

        # ── Fallback 2: dummy socket ──────────────────────────────────
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith('127.'):
                print(f"[IP] Detected {ip} via socket")
                return ip
        except Exception:
            pass

        print("[IP] WARNING: Could not detect LAN IP — using 127.0.0.1")
        return "127.0.0.1"

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port
        }
