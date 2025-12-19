"""
AI_TEAM Monitor MVP — Минимальный интерфейс для общения с Оркестратором.

Версия: 0.1 (MVP / Proof of Concept)
Спецификация: docs/concepts/drafts/MONITOR_MVP_SPEC_v0.1.md

Страницы:
- / — Главная: диалог с Оркестратором + лента выполнения
- /agents — Реестр агентов
- /agents/{name} — Паспорт агента

Usage:
    ./venv/bin/python -m src.web.monitor_mvp

Then open http://localhost:8080 in browser.
"""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import yaml

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Application State
# =============================================================================

app = FastAPI(title="AI_TEAM Monitor MVP", version="0.1.0")

# In-memory storage
registered_agents: Dict[str, Dict[str, Any]] = {}
chat_messages: List[Dict[str, Any]] = []  # Диалог с Оркестратором
feed_events: List[Dict[str, Any]] = []    # Лента выполнения
processed_message_ids: set = set()

# WebSocket connections
ws_connections: List[WebSocket] = []

# MindBus connections
bus_listener: Optional[MindBus] = None
bus_sender: Optional[MindBus] = None
bus_thread: Optional[threading.Thread] = None

MONITOR_REPLY_QUEUE = "monitor.replies"

# Current task state
current_task: Optional[Dict[str, Any]] = None


# =============================================================================
# Agent Registry
# =============================================================================

def load_agents_from_config() -> Dict[str, Dict[str, Any]]:
    """Load agent configurations from config/agents/*.yaml"""
    agents = {}
    config_dir = Path(__file__).parent.parent.parent / "config" / "agents"

    if not config_dir.exists():
        logger.warning(f"Config directory not found: {config_dir}")
        return agents

    for config_file in config_dir.glob("*.yaml"):
        try:
            with open(config_file) as f:
                config = yaml.safe_load(f)

            # Extract agent config (handle nested structure)
            if len(config) == 1:
                agent_key = list(config.keys())[0]
                agent_config = config[agent_key]
            else:
                agent_config = config

            name = agent_config.get("name", config_file.stem)
            display = agent_config.get("display", {})

            # Get capabilities with descriptions
            capabilities = []
            for cap in agent_config.get("capabilities", []):
                if isinstance(cap, str):
                    capabilities.append({"name": cap, "description": ""})
                elif isinstance(cap, dict):
                    capabilities.append({
                        "name": cap.get("name", ""),
                        "description": cap.get("description", "")
                    })

            # Get LLM config
            llm_config = agent_config.get("llm", {})

            agents[name] = {
                "name": name,
                "display_name": display.get("name", name),
                "display_avatar": display.get("avatar", "🤖"),
                "display_description": display.get("description", ""),
                "role_in_team": display.get("role_in_team", ""),
                "type": agent_config.get("type", "agent"),
                "version": agent_config.get("version", "1.0.0"),
                "capabilities": capabilities,
                "llm_model": llm_config.get("model", "unknown"),
                "llm_temperature": llm_config.get("temperature", 0.7),
                "system_prompt": agent_config.get("prompts", {}).get("system", ""),
                "status": "offline",
                "last_heartbeat": None,
                "config": agent_config,
            }

            logger.info(f"Loaded agent config: {name}")

        except Exception as e:
            logger.error(f"Error loading {config_file}: {e}")

    return agents


def initialize_agents():
    """Initialize agents from config files."""
    global registered_agents
    registered_agents = load_agents_from_config()
    logger.info(f"Loaded {len(registered_agents)} agent configurations")


# =============================================================================
# MindBus Integration
# =============================================================================

def add_feed_event(event_type: str, agent_name: str, description: str,
                   metadata: Optional[Dict] = None):
    """Add event to execution feed."""
    event = {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "agent": agent_name,
        "agent_display": registered_agents.get(agent_name, {}).get("display_name", agent_name),
        "agent_avatar": registered_agents.get(agent_name, {}).get("display_avatar", "🤖"),
        "description": description,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    feed_events.append(event)

    # Keep only last 100 events
    if len(feed_events) > 100:
        feed_events.pop(0)

    # Broadcast to WebSocket clients
    asyncio.run(broadcast_update({
        "type": "feed",
        "event": event
    }))


def on_event(event: dict, data: dict) -> None:
    """Handle incoming EVENT messages."""
    event_type = data.get("event_type", "") or event.get("type", "")

    if "node.registered" in event_type:
        event_data = data.get("event_data", data)
        node_name = event_data.get("name", "")
        if node_name:
            if node_name not in registered_agents:
                registered_agents[node_name] = {
                    "name": node_name,
                    "display_name": node_name,
                    "display_avatar": "🤖",
                    "status": "online",
                }
            registered_agents[node_name]["status"] = "online"
            registered_agents[node_name]["last_heartbeat"] = datetime.utcnow().isoformat()
            logger.info(f"Agent registered: {node_name}")

            asyncio.run(broadcast_update({
                "type": "agent_status",
                "agent": node_name,
                "status": "online"
            }))

    elif "node.heartbeat" in event_type:
        event_data = data.get("event_data", data)
        node_name = event_data.get("name", "")
        if node_name and node_name in registered_agents:
            current_status = registered_agents[node_name].get("status", "offline")
            if current_status != "working":
                registered_agents[node_name]["status"] = "online"
            registered_agents[node_name]["last_heartbeat"] = datetime.utcnow().isoformat()

    elif "node.deregistered" in event_type:
        event_data = data.get("event_data", data)
        node_name = event_data.get("name", "")
        if node_name and node_name in registered_agents:
            registered_agents[node_name]["status"] = "offline"
            logger.info(f"Agent deregistered: {node_name}")


def on_task_event(event: dict, data: dict) -> None:
    """Handle task events for feed."""
    event_type = data.get("event_type", "")
    source = event.get("source", "")
    event_data = data.get("event_data", {})

    if "task.progress" in event_type:
        state = event_data.get("state", "")
        task_desc = event_data.get("description", "")

        if source and source in registered_agents:
            if state == "working":
                registered_agents[source]["status"] = "working"
                add_feed_event(
                    "working",
                    source,
                    task_desc or "работает...",
                    {"state": state}
                )
                asyncio.run(broadcast_update({
                    "type": "agent_status",
                    "agent": source,
                    "status": "working"
                }))


def on_result(event: dict, data: dict) -> None:
    """Handle incoming RESULT messages."""
    message_id = event.get("id")
    source = event.get("source", "unknown")

    if message_id and message_id in processed_message_ids:
        return
    if message_id:
        processed_message_ids.add(message_id)

    # Extract result info
    output = data.get("output", {})
    if isinstance(output, dict):
        agent_output = output.get("output", {})
        word_count = agent_output.get("word_count", 0) if isinstance(agent_output, dict) else 0
        text = agent_output.get("text", "") if isinstance(agent_output, dict) else str(agent_output)
    else:
        word_count = 0
        text = str(output)

    metrics = data.get("metrics", output.get("metrics", {})) if isinstance(output, dict) else {}
    exec_time = metrics.get("execution_time_seconds", 0)

    # Add to feed
    add_feed_event(
        "completed",
        source,
        f"готово ({word_count} слов, {exec_time:.1f}с)" if word_count else "готово",
        {"word_count": word_count, "exec_time": exec_time}
    )

    # Update agent status
    if source in registered_agents:
        registered_agents[source]["status"] = "online"
        asyncio.run(broadcast_update({
            "type": "agent_status",
            "agent": source,
            "status": "online"
        }))

    # If this is from Orchestrator, add to chat
    if source == "orchestrator" or "orchestrator" in source.lower():
        chat_messages.append({
            "id": message_id,
            "role": "assistant",
            "content": text[:500] + "..." if len(text) > 500 else text,
            "full_content": text,
            "timestamp": datetime.utcnow().isoformat(),
        })
        asyncio.run(broadcast_update({
            "type": "chat_message",
            "message": chat_messages[-1]
        }))

    logger.info(f"Received RESULT from {source}")


def on_error(event: dict, data: dict) -> None:
    """Handle incoming ERROR messages."""
    message_id = event.get("id")
    source = event.get("source", "unknown")

    if message_id and message_id in processed_message_ids:
        return
    if message_id:
        processed_message_ids.add(message_id)

    error_msg = data.get("message", data.get("error", str(data)))

    # Add to feed
    add_feed_event(
        "error",
        source,
        f"ошибка — {error_msg[:50]}",
        {"error": error_msg}
    )

    # Update agent status
    if source in registered_agents:
        registered_agents[source]["status"] = "online"
        asyncio.run(broadcast_update({
            "type": "agent_status",
            "agent": source,
            "status": "online"
        }))

    logger.info(f"Received ERROR from {source}")


def start_bus_connections():
    """Start MindBus connections."""
    global bus_listener, bus_sender, bus_thread

    bus_sender = MindBus()
    bus_sender.connect()
    logger.info("MindBus sender connection established")

    bus_listener = MindBus()
    bus_listener.connect()

    bus_listener.subscribe("evt.node.#", on_event)
    bus_listener.subscribe("evt.task.#", on_task_event)
    bus_listener.subscribe_queue(MONITOR_REPLY_QUEUE, on_result)

    logger.info("MindBus listener started")

    def consume_loop():
        try:
            bus_listener.start_consuming()
        except Exception as e:
            logger.error(f"Bus consume error: {e}")

    bus_thread = threading.Thread(target=consume_loop, daemon=True)
    bus_thread.start()


# =============================================================================
# WebSocket
# =============================================================================

async def broadcast_update(data: dict):
    """Broadcast update to all WebSocket clients."""
    message = json.dumps(data)
    disconnected = []

    for ws in ws_connections:
        try:
            await ws.send_text(message)
        except:
            disconnected.append(ws)

    for ws in disconnected:
        if ws in ws_connections:
            ws_connections.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    ws_connections.append(websocket)
    logger.info("WebSocket client connected")

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_connections:
            ws_connections.remove(websocket)
        logger.info("WebSocket client disconnected")


# =============================================================================
# REST API
# =============================================================================

@app.get("/api/agents")
async def get_agents():
    """Get list of all agents."""
    return JSONResponse([
        {
            "name": a.get("name"),
            "display_name": a.get("display_name"),
            "display_avatar": a.get("display_avatar", "🤖"),
            "type": a.get("type"),
            "status": a.get("status", "offline"),
        }
        for a in registered_agents.values()
    ])


@app.get("/api/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get full agent details."""
    if agent_name not in registered_agents:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    return JSONResponse(registered_agents[agent_name])


@app.get("/api/chat")
async def get_chat():
    """Get chat history."""
    return JSONResponse(chat_messages[-50:])


@app.get("/api/feed")
async def get_feed():
    """Get execution feed."""
    return JSONResponse(feed_events[-50:])


@app.post("/api/chat")
async def send_chat(message: dict):
    """Send message to Orchestrator."""
    global current_task

    content = message.get("content", "").strip()
    if not content:
        return JSONResponse({"error": "Content is required"}, status_code=400)

    # Add user message to chat
    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    chat_messages.append(user_msg)

    # Broadcast to WebSocket
    await broadcast_update({
        "type": "chat_message",
        "message": user_msg
    })

    # Send to Orchestrator via MindBus
    try:
        if bus_sender is None or bus_sender._connection is None or bus_sender._connection.is_closed:
            new_bus = MindBus()
            new_bus.connect()
            globals()['bus_sender'] = new_bus

        command_id = str(uuid.uuid4())
        current_task = {"id": command_id, "content": content}

        bus_sender.send_command(
            action="process_request",
            params={"request": content},
            target="orchestrator.task",
            target_id="orchestrator",
            source="monitor",
            reply_to=MONITOR_REPLY_QUEUE,
            context={"target_node": "orchestrator"},
        )

        # Add assistant "thinking" message
        thinking_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": "Понял задачу. Обрабатываю...",
            "timestamp": datetime.utcnow().isoformat(),
        }
        chat_messages.append(thinking_msg)
        await broadcast_update({
            "type": "chat_message",
            "message": thinking_msg
        })

        return JSONResponse({"success": True, "command_id": command_id})

    except Exception as e:
        logger.error(f"Error sending to Orchestrator: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/stop")
async def stop_task():
    """Stop current task."""
    global current_task

    if current_task:
        add_feed_event("cancelled", "system", "Задача отменена пользователем")
        current_task = None
        return JSONResponse({"success": True, "message": "Task cancelled"})

    return JSONResponse({"success": False, "message": "No active task"})


# =============================================================================
# HTML Pages
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Main page - Chat with Orchestrator."""
    return get_main_html()


@app.get("/agents", response_class=HTMLResponse)
async def agents_page():
    """Agent registry page."""
    return get_agents_html()


@app.get("/agents/{agent_name}", response_class=HTMLResponse)
async def agent_detail_page(agent_name: str):
    """Agent passport page."""
    if agent_name not in registered_agents:
        return HTMLResponse("<h1>Agent not found</h1>", status_code=404)
    return get_agent_passport_html(agent_name)


def get_main_html() -> str:
    """Main page HTML - Chat + Feed."""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI_TEAM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --bg-input: #0f0f23;
            --text-primary: #e0e0e0;
            --text-secondary: #8892b0;
            --accent: #4a90a4;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
            --border: #2d3748;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        header {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo {
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--accent);
        }

        .header-actions {
            display: flex;
            gap: 12px;
            align-items: center;
        }

        .header-actions a {
            color: var(--text-secondary);
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 6px;
            transition: all 0.2s;
        }

        .header-actions a:hover {
            background: var(--bg-input);
            color: var(--text-primary);
        }

        .stop-btn {
            background: var(--error);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
            display: none;
        }

        .stop-btn.visible { display: block; }
        .stop-btn:hover { opacity: 0.9; }

        /* Main content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
            padding: 20px;
            overflow: hidden;
        }

        /* Chat area */
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
        }

        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        .message {
            margin-bottom: 16px;
            display: flex;
            gap: 12px;
        }

        .message.user {
            flex-direction: row-reverse;
        }

        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: var(--bg-input);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            flex-shrink: 0;
        }

        .message.user .message-avatar {
            background: var(--accent);
        }

        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 12px;
            background: var(--bg-input);
        }

        .message.user .message-content {
            background: var(--accent);
            color: white;
        }

        /* Feed section */
        .feed-section {
            border-top: 1px solid var(--border);
            padding: 12px 20px;
            max-height: 200px;
            overflow-y: auto;
        }

        .feed-title {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .feed-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 0;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .feed-icon {
            font-size: 1rem;
        }

        .feed-agent {
            color: var(--text-primary);
            font-weight: 500;
        }

        .feed-item.error .feed-agent,
        .feed-item.error .feed-desc {
            color: var(--error);
        }

        .feed-item.completed .feed-icon { color: var(--success); }
        .feed-item.working .feed-icon { color: var(--warning); }
        .feed-item.error .feed-icon { color: var(--error); }

        /* Input area */
        .input-area {
            border-top: 1px solid var(--border);
            padding: 16px 20px;
            display: flex;
            gap: 12px;
        }

        .input-area input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--bg-input);
            color: var(--text-primary);
            font-size: 1rem;
        }

        .input-area input:focus {
            outline: none;
            border-color: var(--accent);
        }

        .input-area input::placeholder {
            color: var(--text-secondary);
        }

        .input-area button {
            padding: 12px 24px;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
        }

        .input-area button:hover { opacity: 0.9; }
        .input-area button:disabled { opacity: 0.5; cursor: not-allowed; }

        /* Empty state */
        .empty-state {
            text-align: center;
            color: var(--text-secondary);
            padding: 60px 20px;
        }

        .empty-state h2 {
            font-size: 1.5rem;
            margin-bottom: 8px;
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">AI_TEAM</div>
        <div class="header-actions">
            <a href="/agents">Агенты</a>
            <button class="stop-btn" id="stop-btn" onclick="stopTask()">🔴 Stop</button>
        </div>
    </header>

    <div class="main-content">
        <div class="chat-container">
            <div class="messages" id="messages">
                <div class="empty-state">
                    <h2>Добро пожаловать в AI_TEAM</h2>
                    <p>Напишите задачу для Оркестратора</p>
                </div>
            </div>

            <div class="feed-section" id="feed-section" style="display: none;">
                <div class="feed-title">Лента выполнения</div>
                <div id="feed-items"></div>
            </div>

            <div class="input-area">
                <input type="text" id="message-input" placeholder="Напишите задачу..." />
                <button id="send-btn" onclick="sendMessage()">Отправить</button>
            </div>
        </div>
    </div>

    <script>
        let ws;
        let chatMessages = [];
        let feedEvents = [];
        let isProcessing = false;

        const feedIcons = {
            'task_assigned': '📋',
            'working': '🔄',
            'completed': '✅',
            'error': '❌',
            'cancelled': '⏹️',
        };

        async function loadData() {
            try {
                const [chatRes, feedRes] = await Promise.all([
                    fetch('/api/chat'),
                    fetch('/api/feed')
                ]);
                chatMessages = await chatRes.json();
                feedEvents = await feedRes.json();
                renderMessages();
                renderFeed();
            } catch (e) {
                console.error('Error loading data:', e);
            }
        }

        function renderMessages() {
            const container = document.getElementById('messages');

            if (chatMessages.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <h2>Добро пожаловать в AI_TEAM</h2>
                        <p>Напишите задачу для Оркестратора</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = chatMessages.map(msg => `
                <div class="message ${msg.role}">
                    <div class="message-avatar">${msg.role === 'user' ? '👤' : '🤖'}</div>
                    <div class="message-content">${escapeHtml(msg.content)}</div>
                </div>
            `).join('');

            container.scrollTop = container.scrollHeight;
        }

        function renderFeed() {
            const section = document.getElementById('feed-section');
            const container = document.getElementById('feed-items');

            if (feedEvents.length === 0) {
                section.style.display = 'none';
                return;
            }

            section.style.display = 'block';

            // Show last 10 events, newest first
            const recentEvents = [...feedEvents].slice(-10).reverse();

            container.innerHTML = recentEvents.map(evt => `
                <div class="feed-item ${evt.type}">
                    <span class="feed-icon">${feedIcons[evt.type] || '📌'}</span>
                    <span class="feed-agent">${evt.agent_display || evt.agent}:</span>
                    <span class="feed-desc">${escapeHtml(evt.description)}</span>
                </div>
            `).join('');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function sendMessage() {
            const input = document.getElementById('message-input');
            const btn = document.getElementById('send-btn');
            const content = input.value.trim();

            if (!content) return;

            input.value = '';
            btn.disabled = true;
            isProcessing = true;
            document.getElementById('stop-btn').classList.add('visible');

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                });

                if (!response.ok) {
                    const error = await response.json();
                    alert('Ошибка: ' + (error.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Ошибка отправки: ' + e.message);
            } finally {
                btn.disabled = false;
            }
        }

        async function stopTask() {
            try {
                await fetch('/api/stop', { method: 'POST' });
                isProcessing = false;
                document.getElementById('stop-btn').classList.remove('visible');
            } catch (e) {
                console.error('Error stopping task:', e);
            }
        }

        function connectWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'chat_message') {
                    chatMessages.push(data.message);
                    renderMessages();
                }

                if (data.type === 'feed') {
                    feedEvents.push(data.event);
                    renderFeed();

                    // Check if task completed
                    if (data.event.type === 'completed' || data.event.type === 'error') {
                        isProcessing = false;
                        document.getElementById('stop-btn').classList.remove('visible');
                    }
                }
            };

            ws.onclose = () => {
                setTimeout(connectWebSocket, 3000);
            };
        }

        // Handle Enter key
        document.getElementById('message-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        loadData();
        connectWebSocket();
    </script>
</body>
</html>"""


def get_agents_html() -> str:
    """Agents registry page HTML."""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Агенты - AI_TEAM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --bg-input: #0f0f23;
            --text-primary: #e0e0e0;
            --text-secondary: #8892b0;
            --accent: #4a90a4;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
            --border: #2d3748;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
        }

        header {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
        }

        header a {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 1.2rem;
        }

        header a:hover { color: var(--text-primary); }

        header h1 {
            font-size: 1.2rem;
            font-weight: 500;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        .agents-list {
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
        }

        .agent-row {
            display: flex;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: background 0.2s;
        }

        .agent-row:hover {
            background: var(--bg-input);
        }

        .agent-row:last-child {
            border-bottom: none;
        }

        .agent-avatar {
            font-size: 1.8rem;
            margin-right: 16px;
        }

        .agent-info {
            flex: 1;
        }

        .agent-name {
            font-weight: 500;
            margin-bottom: 4px;
        }

        .agent-id {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-family: monospace;
        }

        .agent-status {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        .status-online { background: var(--success); }
        .status-offline { background: #6b7280; }
        .status-working {
            background: var(--warning);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .status-text {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .agent-arrow {
            color: var(--text-secondary);
            font-size: 1.2rem;
        }

        .summary {
            text-align: center;
            padding: 16px;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <header>
        <a href="/">←</a>
        <h1>Реестр агентов</h1>
    </header>

    <div class="container">
        <div class="agents-list" id="agents-list">
            <div style="padding: 40px; text-align: center; color: var(--text-secondary);">
                Загрузка...
            </div>
        </div>
        <div class="summary" id="summary"></div>
    </div>

    <script>
        let ws;

        async function loadAgents() {
            try {
                const response = await fetch('/api/agents');
                const agents = await response.json();
                renderAgents(agents);
            } catch (e) {
                console.error('Error loading agents:', e);
            }
        }

        function renderAgents(agents) {
            const container = document.getElementById('agents-list');
            const summary = document.getElementById('summary');

            if (agents.length === 0) {
                container.innerHTML = `
                    <div style="padding: 40px; text-align: center; color: var(--text-secondary);">
                        Нет зарегистрированных агентов
                    </div>
                `;
                summary.textContent = '';
                return;
            }

            container.innerHTML = agents.map(agent => `
                <div class="agent-row" onclick="window.location.href='/agents/${agent.name}'">
                    <div class="agent-avatar">${agent.display_avatar || '🤖'}</div>
                    <div class="agent-info">
                        <div class="agent-name">${agent.display_name}</div>
                        <div class="agent-id">${agent.name}</div>
                    </div>
                    <div class="agent-status">
                        <span class="status-dot status-${agent.status}"></span>
                        <span class="status-text">${agent.status}</span>
                    </div>
                    <div class="agent-arrow">→</div>
                </div>
            `).join('');

            const online = agents.filter(a => a.status !== 'offline').length;
            summary.textContent = `Всего: ${agents.length} агентов (${online} online)`;
        }

        function connectWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'agent_status') {
                    loadAgents();
                }
            };

            ws.onclose = () => {
                setTimeout(connectWebSocket, 3000);
            };
        }

        loadAgents();
        connectWebSocket();
        setInterval(loadAgents, 10000);
    </script>
</body>
</html>"""


def get_agent_passport_html(agent_name: str) -> str:
    """Agent passport page HTML."""
    agent = registered_agents.get(agent_name, {})

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{agent.get('display_name', agent_name)} - AI_TEAM</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --bg-input: #0f0f23;
            --text-primary: #e0e0e0;
            --text-secondary: #8892b0;
            --accent: #4a90a4;
            --success: #22c55e;
            --warning: #f59e0b;
            --border: #2d3748;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
        }}

        header {{
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        header a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 1.2rem;
        }}

        header a:hover {{ color: var(--text-primary); }}

        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}

        .agent-header {{
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 24px;
        }}

        .agent-avatar {{
            font-size: 4rem;
        }}

        .agent-title h1 {{
            font-size: 1.8rem;
            margin-bottom: 4px;
        }}

        .agent-desc {{
            color: var(--text-secondary);
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 20px;
            background: var(--bg-input);
            font-size: 0.85rem;
            margin-top: 8px;
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}

        .status-online {{ background: var(--success); }}
        .status-offline {{ background: #6b7280; }}
        .status-working {{ background: var(--warning); }}

        .section {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }}

        .section-title {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }}

        .info-row {{
            display: flex;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }}

        .info-row:last-child {{
            border-bottom: none;
        }}

        .info-label {{
            width: 150px;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .info-value {{
            flex: 1;
            font-family: monospace;
        }}

        .capabilities-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .capability {{
            background: var(--bg-input);
            padding: 10px 14px;
            border-radius: 8px;
        }}

        .capability-name {{
            font-weight: 500;
            color: var(--accent);
        }}

        .capability-desc {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        .prompt-box {{
            background: var(--bg-input);
            border-radius: 8px;
            padding: 16px;
            font-family: monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <header>
        <a href="/agents">← Агенты</a>
    </header>

    <div class="container">
        <div class="agent-header">
            <div class="agent-avatar">{agent.get('display_avatar', '🤖')}</div>
            <div class="agent-title">
                <h1>{agent.get('display_name', agent_name)}</h1>
                <div class="agent-desc">{agent.get('display_description', '')}</div>
                <div class="status-badge" id="status-badge">
                    <span class="status-dot status-{agent.get('status', 'offline')}"></span>
                    <span id="status-text">{agent.get('status', 'offline')}</span>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Идентификация</div>
            <div class="info-row">
                <div class="info-label">Системное имя</div>
                <div class="info-value">{agent_name}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Display Name</div>
                <div class="info-value">{agent.get('display_name', agent_name)}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Роль в команде</div>
                <div class="info-value">{agent.get('role_in_team', '—')}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Тип</div>
                <div class="info-value">{agent.get('type', 'agent')}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Версия</div>
                <div class="info-value">{agent.get('version', '1.0.0')}</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Конфигурация LLM</div>
            <div class="info-row">
                <div class="info-label">Модель</div>
                <div class="info-value">{agent.get('llm_model', 'unknown')}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Температура</div>
                <div class="info-value">{agent.get('llm_temperature', 0.7)}</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Capabilities</div>
            <div class="capabilities-list">
                {''.join(f'''
                <div class="capability">
                    <div class="capability-name">{cap.get('name', cap) if isinstance(cap, dict) else cap}</div>
                    <div class="capability-desc">{cap.get('description', '') if isinstance(cap, dict) else ''}</div>
                </div>
                ''' for cap in agent.get('capabilities', []))}
            </div>
        </div>

        <div class="section">
            <div class="section-title">System Prompt</div>
            <div class="prompt-box">{agent.get('system_prompt', 'Не указан')[:2000]}</div>
        </div>
    </div>

    <script>
        const agentName = '{agent_name}';
        let ws;

        async function loadAgent() {{
            try {{
                const response = await fetch(`/api/agents/${{agentName}}`);
                const agent = await response.json();

                const dot = document.querySelector('.status-dot');
                dot.className = `status-dot status-${{agent.status}}`;
                document.getElementById('status-text').textContent = agent.status;
            }} catch (e) {{
                console.error('Error loading agent:', e);
            }}
        }}

        function connectWebSocket() {{
            ws = new WebSocket(`ws://${{window.location.host}}/ws`);

            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.type === 'agent_status' && data.agent === agentName) {{
                    loadAgent();
                }}
            }};

            ws.onclose = () => {{
                setTimeout(connectWebSocket, 3000);
            }};
        }}

        connectWebSocket();
        setInterval(loadAgent, 5000);
    </script>
</body>
</html>"""


# =============================================================================
# Lifecycle
# =============================================================================

@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    initialize_agents()
    start_bus_connections()


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global bus_listener, bus_sender
    if bus_listener:
        bus_listener.stop_consuming()
        bus_listener.disconnect()
    if bus_sender:
        bus_sender.disconnect()


# =============================================================================
# Main
# =============================================================================

def main():
    """Run the Monitor MVP."""
    print("\n" + "="*60)
    print("AI_TEAM Monitor MVP v0.1")
    print("="*60)
    print("\nStarting web server...")
    print("Open http://localhost:8080 in your browser")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
