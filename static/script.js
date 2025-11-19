const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
const socket = new WebSocket(wsUrl);

const statusEl = document.getElementById('connection-status');
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const terminalLogs = document.getElementById('terminal-logs');
const resourcesGrid = document.getElementById('resources-grid');

// Connection handling
socket.onopen = () => {
    statusEl.textContent = 'Connected';
    statusEl.classList.add('connected');
    addLog('system', 'Connected to server');
};

socket.onclose = () => {
    statusEl.textContent = 'Disconnected';
    statusEl.classList.remove('connected');
    addLog('system', 'Disconnected from server');
};

socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
};

// Sending messages
function sendMessage() {
    const text = userInput.value.trim();
    if (text) {
        socket.send(text);
        userInput.value = '';
    }
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Message handling
function handleMessage(msg) {
    const { type, data } = msg;

    switch (type) {
        case 'log':
            addLog(data.stage, data.message, data.timestamp);
            break;
        case 'chat':
            addChatMessage(data.role, data.content);
            break;
        case 'layer':
            updateLayer(data.name, data.status, data.data);
            break;
        case 'resources':
            displayResources(data.data);
            break;
        case 'open_url':
            // Open URL in new tab
            window.open(data.url, '_blank');
            addChatMessage('system', `Opening: ${data.url}`);
            break;
        case 'tools':
            addLog('system', `Tools loaded: ${data.join(', ')}`);
            break;
    }
}

function addLog(stage, message, timestamp = new Date().toLocaleTimeString()) {
    const div = document.createElement('div');
    div.className = 'log-entry';
    div.innerHTML = `
        <span class="log-time">[${timestamp}]</span>
        <span class="log-stage">[${stage}]</span>
        <span class="log-msg">${message}</span>
    `;
    terminalLogs.appendChild(div);
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

function addChatMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.textContent = content;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function updateLayer(name, status, data) {
    const id = `layer-${name.toLowerCase()}`;
    const card = document.getElementById(id);
    if (!card) return;

    const statusEl = card.querySelector('.layer-status');
    const detailsEl = card.querySelector('.layer-details');

    statusEl.textContent = status === 'active' ? 'Running...' : 'Idle';

    if (status === 'active') {
        card.classList.add('active');
    } else {
        card.classList.remove('active');
    }

    if (data) {
        detailsEl.textContent = JSON.stringify(data, null, 2);
    }
}

function displayResources(data) {
    // Parse the resource data (which might be a string from the tool)
    const div = document.createElement('div');
    div.className = 'resource-card';

    // Try to extract title/url if possible, otherwise just show text
    let content = data;
    let title = "Search Result";

    if (content.includes("Title:")) {
        // Simple parsing for DuckDuckGo results
        const lines = content.split('\n');
        const titleLine = lines.find(l => l.startsWith('Title:'));
        if (titleLine) title = titleLine.replace('Title:', '').trim();
    }

    div.innerHTML = `
        <h4>${title}</h4>
        <p>${content.substring(0, 150)}...</p>
    `;
    resourcesGrid.appendChild(div);
}
