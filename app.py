import eventlet
eventlet.monkey_patch()

import argparse
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import requests

from backend.node import Node
from backend.peer_manager import PeerManager
from backend.discovery import Discovery

app = Flask(__name__)
app.config['SECRET_KEY'] = 'p2p_secret!'
socketio = SocketIO(app, async_mode='eventlet')

# Global state
node = None
peer_manager = PeerManager()
discovery = None
received_messages = set()

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
    data = request.json
    message_id = data.get('message_id')
    sender_id = data.get('sender_id')
    sender_ip = data.get('sender_ip')
    message = data.get('message')
    timestamp = data.get('timestamp')
    
    if message_id in received_messages:
        return jsonify({"status": "duplicate"}), 200
        
    received_messages.add(message_id)
    print(f"RECEIVE {message_id}")
    
    # Broadcast to local frontend
    socketio.emit('receive_message', {
        'message_id': message_id,
        'sender_id': sender_id,
        'sender_ip': sender_ip,
        'message': message,
        'timestamp': timestamp
    })
    
    return jsonify({"status": "success"}), 200

# SocketIO Events for Frontend
@socketio.on('connect')
def handle_connect():
    print("Frontend connected.")

@socketio.on('get_node_info')
def handle_get_node_info():
    socketio.emit('node_info', node.to_dict())

@socketio.on('get_peers')
def handle_get_peers():
    peers = peer_manager.get_all_peers()
    socketio.emit('peers_list', peers)

@socketio.on('send_message')
def handle_send_message(data):
    target_node_id = data.get('target_node_id')
    message = data.get('message')
    message_id = data.get('message_id')
    
    peer = peer_manager.get_peer(target_node_id)
    if not peer:
        socketio.emit('message_error', {'message_id': message_id, 'error': 'Peer not found in local list'})
        return
    
    ping_url = f"http://{peer['ip']}:{peer['port']}/api/ping"
    target_url = f"http://{peer['ip']}:{peer['port']}/api/message"
    
    payload = {
        'message_id': message_id,
        'sender_id': node.node_id,
        'sender_ip': node.ip,
        'message': message,
        'timestamp': time.time()
    }
    
    def send_request():
        # Ping Phase
        try:
            ping_resp = requests.get(ping_url, timeout=1.0)
            if ping_resp.status_code != 200:
                socketio.emit('message_error', {'message_id': message_id, 'error': 'Peer Offline (Ping failed)'})
                return
        except Exception:
            socketio.emit('message_error', {'message_id': message_id, 'error': 'Peer Offline'})
            return

        # Sending Phase
        print(f"SEND {message_id} to {peer['ip']}:{peer['port']}")
        
        success = False
        for attempt in range(3):
            try:
                response = requests.post(target_url, json=payload, timeout=2.0)
                if response.status_code == 200:
                    success = True
                    break
            except Exception:
                pass
                
            time.sleep(0.5) # Wait before retry
            
        if success:
            print(f"ACK {message_id}")
            socketio.emit('message_ack', {'message_id': message_id})
        else:
            socketio.emit('message_error', {'message_id': message_id, 'error': 'Failed to deliver message after 3 retries'})

    # Fire and forget in a background thread
    eventlet.spawn(send_request)

def main():
    global node, discovery
    parser = argparse.ArgumentParser(description="P2P Node")
    parser.add_argument('--port', type=int, default=5000, help="Port to run the web server on")
    args = parser.parse_args()

    node = Node(port=args.port)
    discovery = Discovery(node, peer_manager)
    discovery.start()
    
    print(f"Starting Node {node.node_id} on {node.ip}:{node.port}")
    socketio.run(app, host='0.0.0.0', port=args.port, debug=False)

if __name__ == '__main__':
    main()
