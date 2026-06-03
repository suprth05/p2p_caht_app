let activePeerId = null;
let chatHistories = {}; // node_id -> array of message objects

const peerListEl = document.getElementById('peer-list');
const chatHeaderEl = document.getElementById('chat-header');
const messagesAreaEl = document.getElementById('messages-area');
const messageInputEl = document.getElementById('message-input');
const sendBtnEl = document.getElementById('send-btn');
const chatPlaceholderEl = document.getElementById('chat-placeholder');

socket.on('connect', () => {
    socket.emit('get_peers');
    setInterval(() => {
        socket.emit('get_peers');
    }, 3000);
});

socket.on('peers_list', (peers) => {
    renderPeerList(peers);
});

socket.on('receive_message', (data) => {
    const { sender_id, sender_ip, message, timestamp } = data;
    
    // Store message
    if (!chatHistories[sender_id]) {
        chatHistories[sender_id] = [];
    }
    
    chatHistories[sender_id].push({
        text: message,
        timestamp: timestamp,
        isSent: false
    });
    
    // If we are currently chatting with this peer, update the UI
    if (activePeerId === sender_id) {
        renderMessages(activePeerId);
    } else {
        // Optional: show unread badge
        console.log(`New message from ${sender_id}`);
    }
});

function renderPeerList(peers) {
    if (peers.length === 0) {
        peerListEl.innerHTML = '<div class="empty-state">No peers discovered yet</div>';
        return;
    }
    
    // Keep reference to currently selected to re-select
    let html = '';
    peers.forEach(peer => {
        const isSelected = peer.node_id === activePeerId ? 'selected' : '';
        html += `
            <div class="peer-item ${isSelected}" onclick="selectPeer('${peer.node_id}', '${peer.ip}:${peer.port}')">
                <div class="peer-id">${peer.node_id}</div>
                <div class="peer-ip">${peer.ip}:${peer.port}</div>
            </div>
        `;
    });
    
    peerListEl.innerHTML = html;
}

function selectPeer(nodeId, ipString) {
    activePeerId = nodeId;
    
    // Update UI state
    document.querySelectorAll('.peer-item').forEach(el => el.classList.remove('selected'));
    // Find the one we just clicked and add selected class
    // We re-render via socket anyway, but this gives instant feedback
    
    chatHeaderEl.textContent = `Chatting with: ${ipString}`;
    messageInputEl.disabled = false;
    sendBtnEl.disabled = false;
    
    if (chatPlaceholderEl) {
        chatPlaceholderEl.style.display = 'none';
    }
    
    renderMessages(nodeId);
    messageInputEl.focus();
}

function renderMessages(nodeId) {
    messagesAreaEl.innerHTML = '';
    
    const history = chatHistories[nodeId] || [];
    if (history.length === 0) {
        messagesAreaEl.innerHTML = '<div class="empty-state">No messages yet. Say hi!</div>';
        return;
    }
    
    history.forEach(msg => {
        const msgEl = document.createElement('div');
        msgEl.className = `message ${msg.isSent ? 'sent' : 'received'}`;
        
        const textEl = document.createElement('div');
        textEl.textContent = msg.text;
        
        const time = new Date(msg.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const metaEl = document.createElement('div');
        metaEl.className = 'message-meta';
        metaEl.textContent = time;
        
        msgEl.appendChild(textEl);
        msgEl.appendChild(metaEl);
        messagesAreaEl.appendChild(msgEl);
    });
    
    // Scroll to bottom
    messagesAreaEl.scrollTop = messagesAreaEl.scrollHeight;
}

function sendMessage() {
    if (!activePeerId) return;
    
    const text = messageInputEl.value.trim();
    if (!text) return;
    
    const timestamp = Date.now() / 1000;
    
    // Send to backend
    socket.emit('send_message', {
        target_node_id: activePeerId,
        message: text
    });
    
    // Update local history
    if (!chatHistories[activePeerId]) {
        chatHistories[activePeerId] = [];
    }
    
    chatHistories[activePeerId].push({
        text: text,
        timestamp: timestamp,
        isSent: true
    });
    
    messageInputEl.value = '';
    renderMessages(activePeerId);
}

// Event Listeners
sendBtnEl.addEventListener('click', sendMessage);
messageInputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
