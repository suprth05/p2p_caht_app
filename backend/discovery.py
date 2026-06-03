import socket
import threading
import json
import time

BROADCAST_PORT = 50025

class Discovery:
    def __init__(self, node, peer_manager):
        self.node = node
        self.peer_manager = peer_manager
        self.running = False
        self.broadcast_thread = None
        self.listen_thread = None

    def start(self):
        self.running = True
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.broadcast_thread.start()
        self.listen_thread.start()

    def stop(self):
        self.running = False

    def _broadcast_loop(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Allow reusing address so multiple nodes on localhost can broadcast
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                pass # SO_REUSEPORT might not be available on all OS
                
            payload = json.dumps(self.node.to_dict()).encode('utf-8')
            
            while self.running:
                try:
                    s.sendto(payload, ('<broadcast>', BROADCAST_PORT))
                except Exception as e:
                    print(f"Broadcast error: {e}")
                
                # Prune old peers every broadcast cycle
                self.peer_manager.prune_peers()
                time.sleep(5)

    def _listen_loop(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                pass
            
            s.bind(('', BROADCAST_PORT))
            s.settimeout(1.0)
            
            while self.running:
                try:
                    data, addr = s.recvfrom(1024)
                    peer_info = json.loads(data.decode('utf-8'))
                    
                    # Don't add ourselves
                    if peer_info.get("node_id") != self.node.node_id:
                        self.peer_manager.update_peer(
                            peer_info["node_id"],
                            peer_info["ip"],
                            peer_info["port"]
                        )
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Listen error: {e}")
