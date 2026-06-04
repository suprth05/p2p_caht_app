import eventlet
eventlet.monkey_patch()

import argparse
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import requests

from backend.node import Node
from backend.peer_manager import PeerManager
from backend.discovery import Discovery

app = Flask(__name__)
app.config['SECRET_KEY'] = 'p2p_secret!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

# Global state
node = None
peer_manager = PeerManager()
discovery = None
received_messages = set()

# -------------------------------------------------------------------
# HTTP Routes
# -------------------------------------------------------------------

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/network')
def network():
    return render_template('network.html')

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({
        "status": "ok",
        "node_id": node.node_id
    }), 200

@app.route('/api/diagnostic', methods=['GET'])
def diagnostic():
    target_node_id = request.args.get('node_id')
    if not target_node_id:
        return jsonify({"error": "Missing node_id parameter"}), 400

    peer = peer_manager.get_peer(target_node_id)
    if not peer:
        return jsonify({"error": "Peer not found"}), 404

    return jsonify({
        "local_ip": node.ip,
        "advertised_ip": node.ip,
        "destination_ip": peer['ip'],
        "destination_port": peer['port']
    }), 200

@app.route('/api/message', methods=['POST'])
def receive_message():
    """Called by the remote peer's backend to deliver a message to us."""
    data = request.json
    message_id  = data.get('message_id')
    sender_id   = data.get('sender_id')
    sender_ip   = data.get('sender_ip')
    message     = data.get('message')
    timestamp   = data.get('timestamp')

    # Deduplicate
    if message_id in received_messages:
        return jsonify({"status": "duplicate"}), 200

    received_messages.add(message_id)
    print(f"RECEIVE {message_id} from {sender_id} ({sender_ip})")

    # Push to ALL connected local browser tabs (correct here — this node
    # may have multiple tabs open, and all should see the incoming message)
    socketio.emit('receive_message', {
        'message_id': message_id,
        'sender_id':  sender_id,
        'sender_ip':  sender_ip,
        'message':    message,
        'timestamp':  timestamp
    })

    return jsonify({"status": "success"}), 200

# -------------------------------------------------------------------
# Socket.IO Events (browser ↔ local backend)
# -------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    print(f"Frontend connected: {request.sid}")
    # Immediately send node info to the newly connected client
    emit('node_info', node.to_dict())

@socketio.on('get_node_info')
def handle_get_node_info():
    # emit() with no arguments replies only to the requesting client
    emit('node_info', node.to_dict())

@socketio.on('get_peers')
def handle_get_peers():
    peers = peer_manager.get_all_peers()
    emit('peers_list', peers)

@socketio.on('send_message')
def handle_send_message(data):
    target_node_id = data.get('target_node_id')
    message        = data.get('message')
    message_id     = data.get('message_id')
    caller_sid     = request.sid   # capture NOW, before we leave the handler

    peer = peer_manager.get_peer(target_node_id)
    if not peer:
        emit('message_error', {
            'message_id': message_id,
            'error': 'Peer not found in local list'
        })
        return

    ping_url   = f"http://{peer['ip']}:{peer['port']}/api/ping"
    target_url = f"http://{peer['ip']}:{peer['port']}/api/message"

    payload = {
        'message_id': message_id,
        'sender_id':  node.node_id,
        'sender_ip':  node.ip,
        'message':    message,
        'timestamp':  time.time()
    }

    def send_request():
        try:
            # --- Ping phase ---
            print(f"[MSG] Pinging {peer['ip']}:{peer['port']} ...")
            try:
                ping_resp = requests.get(ping_url, timeout=2.0)
                if ping_resp.status_code != 200:
                    print(f"[MSG] Ping returned {ping_resp.status_code}")
                    socketio.emit('message_error',
                        {'message_id': message_id, 'error': 'Peer Offline (ping failed)'},
                        to=caller_sid)
                    return
                print(f"[MSG] Ping OK")
            except Exception as e:
                print(f"[MSG] Ping failed: {e}")
                socketio.emit('message_error',
                    {'message_id': message_id, 'error': 'Peer Offline'},
                    to=caller_sid)
                return

            # --- Send phase (3 retries) ---
            print(f"SEND {message_id} to {peer['ip']}:{peer['port']}")
            success = False
            last_error = None
            for attempt in range(3):
                try:
                    resp = requests.post(target_url, json=payload, timeout=3.0)
                    if resp.status_code == 200:
                        success = True
                        break
                    last_error = f"HTTP {resp.status_code}"
                except Exception as e:
                    last_error = str(e)
                if attempt < 2:
                    time.sleep(0.5)

            if success:
                print(f"ACK  {message_id}")
                socketio.emit('message_ack', {'message_id': message_id}, to=caller_sid)
            else:
                print(f"[MSG] FAILED {message_id} after 3 retries: {last_error}")
                socketio.emit('message_error',
                    {'message_id': message_id, 'error': f'Failed after 3 retries: {last_error}'},
                    to=caller_sid)
        except Exception as e:
            # Catch-all so the greenthread never dies silently
            print(f"[MSG] UNEXPECTED ERROR in send_request: {e}")
            try:
                socketio.emit('message_error',
                    {'message_id': message_id, 'error': f'Internal error: {e}'},
                    to=caller_sid)
            except Exception:
                pass

    eventlet.spawn(send_request)


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main():
    global node, discovery
    parser = argparse.ArgumentParser(description="P2P Node")
    parser.add_argument('--port', type=int, default=5000,
                        help="Port to run the web server on")
    parser.add_argument('--ip', type=str, default=None,
                        help="Manually set your LAN IP (e.g. 192.168.43.100)")
    args = parser.parse_args()

    node = Node(port=args.port, ip_override=args.ip)
    discovery = Discovery(node, peer_manager)
    discovery.start()

    print(f"Starting Node {node.node_id} on {node.ip}:{node.port}")
    socketio.run(app, host='0.0.0.0', port=args.port, debug=False)

if __name__ == '__main__':
    main()
