import uuid
import socket

class Node:
    def __init__(self, port=5000):
        self.node_id = str(uuid.uuid4())
        self.port = port
        self.ip = self._get_local_ip()

    def _get_local_ip(self):
        try:
            # Create a dummy socket to determine the local IP used for routing
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
