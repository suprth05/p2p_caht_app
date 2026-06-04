#!/usr/bin/env python3
"""Diagnostic: show all network interfaces and IPs."""
import subprocess, socket, json

print("=" * 60)
print("NETWORK DIAGNOSTIC")
print("=" * 60)

# 1. ip -o -4 addr show
print("\n--- ip -o -4 addr show ---")
try:
    out = subprocess.check_output(['ip', '-o', '-4', 'addr', 'show'], stderr=subprocess.DEVNULL).decode()
    print(out)
except Exception as e:
    print(f"FAILED: {e}")

# 2. ip route get 1.1.1.1
print("--- ip route get 1.1.1.1 ---")
try:
    out = subprocess.check_output(['ip', 'route', 'get', '1.1.1.1'], stderr=subprocess.DEVNULL).decode()
    print(out)
except Exception as e:
    print(f"FAILED: {e}")

# 3. hostname -I
print("--- hostname -I ---")
try:
    out = subprocess.check_output(['hostname', '-I'], stderr=subprocess.DEVNULL).decode()
    print(out)
except Exception as e:
    print(f"FAILED: {e}")

# 4. socket method
print("--- socket connect 8.8.8.8 ---")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    print(f"Result: {s.getsockname()[0]}")
    s.close()
except Exception as e:
    print(f"FAILED: {e}")

# 5. netifaces if available
print("\n--- Python netifaces ---")
try:
    import netifaces
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
        for a in addrs:
            print(f"  {iface}: {a['addr']}")
except ImportError:
    print("  netifaces not installed")

# 6. What our Node class picks
print("\n--- Our Node._get_local_ip() result ---")
from backend.node import Node
n = Node.__new__(Node)
n.node_id = "test"
n.port = 9999
result = n._get_local_ip()
print(f"  Selected IP: {result}")
