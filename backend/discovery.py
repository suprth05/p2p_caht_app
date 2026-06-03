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
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                pass

            payload = json.dumps(self.node.to_dict()).encode('utf-8')

            while self.running:
                try:
                    s.sendto(payload, ('<broadcast>', BROADCAST_PORT))
                except Exception as e:
                    print(f"Broadcast error: {e}")

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
                    real_source_ip = addr[0]          # <-- actual network IP
                    peer_info = json.loads(data.decode('utf-8'))

                    # Don't add ourselves
                    if peer_info.get("node_id") == self.node.node_id:
                        continue

                    advertised_ip = peer_info.get("ip", "?")
                    peer_port     = peer_info["port"]

                    # ALWAYS use the real source IP from the UDP packet.
                    # The peer might advertise 127.0.0.1 or 172.17.x.x
                    # (Docker), but addr[0] is the actual LAN address
                    # the packet arrived from.
                    use_ip = real_source_ip

                    if advertised_ip != real_source_ip:
                        print(f"[Discovery] WARNING: Peer {peer_info['node_id'][:8]} "
                              f"advertised {advertised_ip} but packet came from "
                              f"{real_source_ip} — using {real_source_ip}")

                    print(f"[Discovery] Peer: {peer_info['node_id'][:8]}… "
                          f"IP: {use_ip}  Port: {peer_port}")

                    self.peer_manager.update_peer(
                        peer_info["node_id"],
                        use_ip,
                        peer_port
                    )
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Listen error: {e}")
