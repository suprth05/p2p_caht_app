import time
import threading

class PeerManager:
    def __init__(self):
        self.peers = {}  # node_id -> {node_id, ip, port, last_seen}
        self.lock = threading.Lock()

    def update_peer(self, node_id, ip, port):
        with self.lock:
            self.peers[node_id] = {
                "node_id": node_id,
                "ip": ip,
                "port": port,
                "last_seen": time.time()
            }

    def prune_peers(self, timeout=15):
        with self.lock:
            current_time = time.time()
            # Create a list of keys to delete to avoid modifying dict while iterating
            stale_peers = [
                node_id for node_id, peer in self.peers.items()
                if current_time - peer["last_seen"] > timeout
            ]
            for node_id in stale_peers:
                del self.peers[node_id]

    def get_all_peers(self):
        with self.lock:
            return list(self.peers.values())

    def get_peer(self, node_id):
        with self.lock:
            return self.peers.get(node_id)
