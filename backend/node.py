import uuid
import socket

class Node:
    def __init__(self, port=5000):
        self.node_id = str(uuid.uuid4())
        self.port = port
        self.ip = self._get_local_ip()
        print(f"Node started: {self.node_id} {self.ip}:{self.port}")

    def _get_local_ip(self):
        import subprocess
        try:
            # Parse ip command output to filter out virtual/docker interfaces
            output = subprocess.check_output(['ip', '-o', '-4', 'addr', 'show']).decode('utf-8')
            for line in output.split('\n'):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                
                iface = parts[1]
                ip_cidr = parts[3]
                ip = ip_cidr.split('/')[0]
                
                # Reject loopback, docker, and virtual adapters
                ignore_prefixes = ('lo', 'docker', 'veth', 'br-', 'virbr', 'vmnet', 'vboxnet', 'tailscale', 'tun', 'tap', 'wg')
                if iface.startswith(ignore_prefixes):
                    continue
                    
                if ip.startswith('127.') or ip.startswith('169.254.'):
                    continue
                
                # Return the first valid physical/hotspot IP found
                return ip
                
            # Fallback to default routing IP if the above fails
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port
        }
