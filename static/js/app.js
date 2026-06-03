// ─── State ────────────────────────────────────────────────────────────────────
let activePeerId = null;
let activePeerLabel = '';
let chatHistories = {};       // node_id → [{id, text, timestamp, isSent, status, errorText}]
let myNodeId = null;

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const peerListEl    = document.getElementById('peer-list');
const chatHeaderEl  = document.getElementById('chat-header');
const messagesAreaEl = document.getElementById('messages-area');
const messageInputEl = document.getElementById('message-input');
const sendBtnEl     = document.getElementById('send-btn');

// ─── Socket.IO events from backend ───────────────────────────────────────────

socket.on('connect', () => {
    socket.emit('get_node_info');
    socket.emit('get_peers');
    // Poll for updated peer list
    setInterval(() => socket.emit('get_peers'), 3000);
});

socket.on('node_info', (data) => {
    myNodeId = data.node_id;
});

socket.on('peers_list', (peers) => {
    renderPeerList(peers);
});

socket.on('receive_message', (data) => {
    const { message_id, sender_id, message, timestamp } = data;

    if (!chatHistories[sender_id]) chatHistories[sender_id] = [];

    // Guard against duplicates (shouldn't happen but be safe)
    if (chatHistories[sender_id].some(m => m.id === message_id)) return;

    chatHistories[sender_id].push({
        id:        message_id,
        text:      message,
        timestamp: timestamp,
        isSent:    false,
        status:    'received'
    });

    if (activePeerId === sender_id) {
        appendMessage(chatHistories[sender_id].at(-1));
        scrollToBottom();
    } else {
        // Mark peer with an unread dot
        markUnread(sender_id);
    }
});

socket.on('message_ack', (data) => {
    updateMessageStatus(data.message_id, 'delivered');
});

socket.on('message_error', (data) => {
    updateMessageStatus(data.message_id, 'failed', data.error);
});

// ─── Rendering helpers ────────────────────────────────────────────────────────

function renderPeerList(peers) {
    if (peers.length === 0) {
        peerListEl.innerHTML = '<div class="empty-state">No peers discovered yet</div>';
        return;
    }

    peerListEl.innerHTML = '';
    peers.forEach(peer => {
        const item = document.createElement('div');
        item.className = 'peer-item' + (peer.node_id === activePeerId ? ' selected' : '');
        item.dataset.nodeId = peer.node_id;

        const timeSince = (Date.now() / 1000) - peer.last_seen;
        const online = timeSince < 12;

        item.innerHTML = `
            <div style="display:flex;align-items:center;gap:8px">
                <span class="online-dot ${online ? 'dot-online' : 'dot-offline'}"></span>
                <div>
                    <div class="peer-id">${peer.node_id.substring(0, 8)}…</div>
                    <div class="peer-ip">${peer.ip}:${peer.port}</div>
                </div>
            </div>`;

        item.addEventListener('click', () => selectPeer(peer.node_id, `${peer.ip}:${peer.port}`));
        peerListEl.appendChild(item);
    });
}

function markUnread(nodeId) {
    const item = peerListEl.querySelector(`[data-node-id="${nodeId}"]`);
    if (item && !item.querySelector('.unread-badge')) {
        const badge = document.createElement('span');
        badge.className = 'unread-badge';
        badge.textContent = '●';
        item.appendChild(badge);
    }
}

function selectPeer(nodeId, ipString) {
    activePeerId   = nodeId;
    activePeerLabel = ipString;

    // Clear the old selected class
    document.querySelectorAll('.peer-item').forEach(el => el.classList.remove('selected'));
    const item = peerListEl.querySelector(`[data-node-id="${nodeId}"]`);
    if (item) {
        item.classList.add('selected');
        // Remove unread badge
        item.querySelector('.unread-badge')?.remove();
    }

    chatHeaderEl.textContent = `Chatting with: ${ipString}`;
    messageInputEl.disabled  = false;
    sendBtnEl.disabled       = false;

    // Render full history
    messagesAreaEl.innerHTML = '';
    const history = chatHistories[nodeId] || [];
    if (history.length === 0) {
        messagesAreaEl.innerHTML = '<div class="empty-state">No messages yet. Say hi!</div>';
    } else {
        history.forEach(appendMessage);
    }
    scrollToBottom();
    messageInputEl.focus();
}

function buildMessageEl(msg) {
    const el = document.createElement('div');
    el.className  = `message ${msg.isSent ? 'sent' : 'received'}`;
    el.dataset.id = msg.id;

    const timeStr = new Date(msg.timestamp * 1000)
        .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let statusHtml = '';
    if (msg.isSent) {
        if      (msg.status === 'pending')   statusHtml = '<span class="status-pending">Sending…</span>';
        else if (msg.status === 'delivered') statusHtml = '<span class="status-delivered">✓ Delivered</span>';
        else if (msg.status === 'failed')    statusHtml = `<span class="status-failed">✗ ${msg.errorText || 'Failed'}</span>`;
    }

    el.innerHTML = `
        <div class="msg-text">${escapeHtml(msg.text)}</div>
        <div class="message-meta">${timeStr}${statusHtml ? ' &nbsp;' + statusHtml : ''}</div>`;
    return el;
}

function appendMessage(msg) {
    // Remove "no messages" placeholder if present
    const placeholder = messagesAreaEl.querySelector('.empty-state');
    if (placeholder) placeholder.remove();

    messagesAreaEl.appendChild(buildMessageEl(msg));
}

function updateMessageStatus(messageId, status, errorText) {
    // Search ALL peer histories (ACK may arrive after user switched peers)
    for (const peerId in chatHistories) {
        const msg = chatHistories[peerId].find(m => m.id === messageId);
        if (msg) {
            msg.status    = status;
            msg.errorText = errorText;

            // Only update DOM if this peer's chat is currently visible
            if (peerId === activePeerId) {
                const el = messagesAreaEl.querySelector(`[data-id="${messageId}"]`);
                if (el) {
                    const timeStr = new Date(msg.timestamp * 1000)
                        .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                    let statusHtml = '';
                    if (status === 'delivered') statusHtml = '<span class="status-delivered">✓ Delivered</span>';
                    if (status === 'failed')    statusHtml = `<span class="status-failed">✗ ${errorText || 'Failed'}</span>`;

                    el.querySelector('.message-meta').innerHTML =
                        `${timeStr}${statusHtml ? ' &nbsp;' + statusHtml : ''}`;
                }
            }
            break;
        }
    }
}

function scrollToBottom() {
    messagesAreaEl.scrollTop = messagesAreaEl.scrollHeight;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ─── Send ─────────────────────────────────────────────────────────────────────

function sendMessage() {
    if (!activePeerId) return;

    const text = messageInputEl.value.trim();
    if (!text) return;

    const messageId = crypto.randomUUID();
    const timestamp = Date.now() / 1000;

    const msgObj = {
        id:        messageId,
        text:      text,
        timestamp: timestamp,
        isSent:    true,
        status:    'pending'
    };

    if (!chatHistories[activePeerId]) chatHistories[activePeerId] = [];
    chatHistories[activePeerId].push(msgObj);

    appendMessage(msgObj);
    scrollToBottom();

    messageInputEl.value = '';

    socket.emit('send_message', {
        message_id:     messageId,
        target_node_id: activePeerId,
        message:        text
    });
}

// ─── Event Listeners ──────────────────────────────────────────────────────────

sendBtnEl.addEventListener('click', sendMessage);
messageInputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
