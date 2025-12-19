"""
AI_TEAM Monitor — Web interface for debugging and monitoring agents.

Features:
- Registry view: list of all registered agents with status
- Agent page: passport info + chat interface
- Send COMMAND messages to agents
- Receive RESULT/ERROR responses via WebSocket

Usage:
    ./venv/bin/python -m src.web.monitor

Then open http://localhost:8080 in browser.

See: docs/SSOT/AGENT_SPEC_v1.0.md
"""

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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

app = FastAPI(title="AI_TEAM Monitor", version="1.0.0")

# Initialize agents on module load (for both runtime and testing)
_initialized = False

# In-memory storage for agents and messages
registered_agents: Dict[str, Dict[str, Any]] = {}
agent_messages: Dict[str, List[Dict[str, Any]]] = {}  # agent_name -> messages
pending_responses: Dict[str, asyncio.Future] = {}  # correlation_id -> future
processed_message_ids: set = set()  # Deduplication: track processed message IDs

# WebSocket connections for live updates
ws_connections: List[WebSocket] = []

# MindBus connections (separate for thread safety)
bus_listener: Optional[MindBus] = None  # For receiving events (runs in background thread)
bus_sender: Optional[MindBus] = None    # For sending commands (used from API endpoints)
bus_thread: Optional[threading.Thread] = None

# Fixed reply queue for RPC responses
MONITOR_REPLY_QUEUE = "monitor.replies"


# =============================================================================
# Agent Registry (load from config files)
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

            # Get capabilities
            capabilities = []
            for cap in agent_config.get("capabilities", []):
                if isinstance(cap, str):
                    capabilities.append(cap)
                elif isinstance(cap, dict):
                    capabilities.append(cap.get("name", ""))

            agents[name] = {
                "name": name,
                "display_name": display.get("name", name),
                "description": display.get("description", ""),
                "type": agent_config.get("type", "agent"),
                "version": agent_config.get("version", "1.0.0"),
                "capabilities": capabilities,
                "tools": agent_config.get("tools", {}).get("enabled", []),
                "status": "offline",  # Will be updated by heartbeat
                "last_heartbeat": None,
                "config": agent_config,
            }

            logger.info(f"Loaded agent config: {name}")

        except Exception as e:
            logger.error(f"Error loading {config_file}: {e}")

    return agents


def initialize_agents():
    """Initialize agents from config files."""
    global registered_agents, _initialized
    if _initialized:
        return
    registered_agents = load_agents_from_config()
    _initialized = True
    logger.info(f"Loaded {len(registered_agents)} agent configurations")


# Auto-initialize on module import
initialize_agents()


# =============================================================================
# MindBus Integration
# =============================================================================

def on_event(event: dict, data: dict) -> None:
    """Handle incoming EVENT messages (registration, heartbeat, etc.)"""
    # CloudEvents type is "ai.team.event", actual event type is in data['event_type']
    event_type = data.get("event_type", "") or event.get("type", "")
    logger.info(f"on_event called: event_type={event_type}")

    if "node.registered" in event_type:
        # Agent registered - data is in event_data
        event_data = data.get("event_data", data)
        node_name = event_data.get("name", "")
        if node_name:
            if node_name not in registered_agents:
                registered_agents[node_name] = {
                    "name": node_name,
                    "display_name": node_name,
                    "status": "online",
                }
            registered_agents[node_name]["status"] = "online"
            registered_agents[node_name]["last_heartbeat"] = datetime.utcnow().isoformat()
            registered_agents[node_name]["passport"] = event_data.get("passport", {})
            logger.info(f"Agent registered: {node_name}")

            # Notify WebSocket clients
            asyncio.run(broadcast_update({
                "type": "agent_status",
                "agent": node_name,
                "status": "online"
            }))

    elif "node.heartbeat" in event_type:
        # Agent heartbeat - data is in event_data
        event_data = data.get("event_data", data)
        node_name = event_data.get("name", "")
        if node_name and node_name in registered_agents:
            # Don't overwrite "working" status with "online" (AGENT_SPEC v1.0.3)
            # Status is set to "online" only by RESULT/ERROR handlers
            current_status = registered_agents[node_name].get("status", "offline")
            if current_status != "working":
                registered_agents[node_name]["status"] = "online"
            registered_agents[node_name]["last_heartbeat"] = datetime.utcnow().isoformat()

    elif "node.deregistered" in event_type:
        # Agent deregistered - data is in event_data
        event_data = data.get("event_data", data)
        node_name = event_data.get("name", "")
        if node_name and node_name in registered_agents:
            registered_agents[node_name]["status"] = "offline"
            logger.info(f"Agent deregistered: {node_name}")


def on_task_event(event: dict, data: dict) -> None:
    """Handle incoming task events (task.progress, etc.) - AGENT_SPEC v1.0.3"""
    event_type = data.get("event_type", "")
    source = event.get("source", "")

    if "task.progress" in event_type:
        # Agent is actively working on a task
        event_data = data.get("event_data", {})
        state = event_data.get("state", "")

        if source and source in registered_agents:
            if state == "working":
                registered_agents[source]["status"] = "working"
                # Broadcast status change to WebSocket clients
                asyncio.run(broadcast_update({
                    "type": "agent_status",
                    "agent": source,
                    "status": "working"
                }))
                logger.info(f"Agent {source} is working (task.progress received)")


def on_result(event: dict, data: dict) -> None:
    """Handle incoming RESULT messages."""
    message_id = event.get("id")
    correlation_id = event.get("correlation_id")
    source = event.get("source", "unknown")

    # Deduplication: skip if already processed
    if message_id and message_id in processed_message_ids:
        logger.debug(f"Skipping duplicate RESULT message: {message_id}")
        return
    if message_id:
        processed_message_ids.add(message_id)

    message = {
        "id": message_id,
        "type": "result",
        "from": source,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    # Store in message history
    if source not in agent_messages:
        agent_messages[source] = []
    agent_messages[source].append(message)

    # Resolve pending future if exists
    if correlation_id and correlation_id in pending_responses:
        future = pending_responses.pop(correlation_id)
        if not future.done():
            future.set_result(message)

    logger.info(f"Received RESULT from {source}")

    # Set agent status back to "online" after processing
    if source in registered_agents:
        registered_agents[source]["status"] = "online"

    # Broadcast to WebSocket clients
    asyncio.run(broadcast_update({
        "type": "message",
        "agent": source,
        "message": message
    }))
    # Also broadcast status change
    asyncio.run(broadcast_update({
        "type": "agent_status",
        "agent": source,
        "status": "online"
    }))


def on_error(event: dict, data: dict) -> None:
    """Handle incoming ERROR messages."""
    message_id = event.get("id")
    correlation_id = event.get("correlation_id")
    source = event.get("source", "unknown")

    # Deduplication: skip if already processed
    if message_id and message_id in processed_message_ids:
        logger.debug(f"Skipping duplicate ERROR message: {message_id}")
        return
    if message_id:
        processed_message_ids.add(message_id)

    message = {
        "id": event.get("id"),
        "type": "error",
        "from": source,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    # Store in message history
    if source not in agent_messages:
        agent_messages[source] = []
    agent_messages[source].append(message)

    # Resolve pending future if exists
    if correlation_id and correlation_id in pending_responses:
        future = pending_responses.pop(correlation_id)
        if not future.done():
            future.set_result(message)

    logger.info(f"Received ERROR from {source}")

    # Set agent status back to "online" after processing (even on error)
    if source in registered_agents:
        registered_agents[source]["status"] = "online"

    # Broadcast to WebSocket clients
    asyncio.run(broadcast_update({
        "type": "message",
        "agent": source,
        "message": message
    }))
    # Also broadcast status change
    asyncio.run(broadcast_update({
        "type": "agent_status",
        "agent": source,
        "status": "online"
    }))


def start_bus_connections():
    """Start MindBus connections - separate for sending and receiving (thread safety)."""
    global bus_listener, bus_sender, bus_thread

    # Sender connection - used from API endpoints (main thread)
    bus_sender = MindBus()
    bus_sender.connect()
    logger.info("MindBus sender connection established")

    # Listener connection - used in background thread
    bus_listener = MindBus()
    bus_listener.connect()

    # Subscribe to events (via topic exchange)
    bus_listener.subscribe("evt.node.#", on_event)  # Use # for multi-word wildcard
    bus_listener.subscribe("evt.task.#", on_task_event)  # Task progress events (AGENT_SPEC v1.0.3)

    # Subscribe to direct reply queue for RPC responses (RESULT/ERROR)
    # This is a direct queue subscription, not via exchange
    bus_listener.subscribe_queue(MONITOR_REPLY_QUEUE, on_result)

    logger.info("MindBus listener started")

    # Start consuming in background
    def consume_loop():
        try:
            bus_listener.start_consuming()
        except Exception as e:
            logger.error(f"Bus consume error: {e}")

    bus_thread = threading.Thread(target=consume_loop, daemon=True)
    bus_thread.start()


# =============================================================================
# WebSocket for Live Updates
# =============================================================================

async def broadcast_update(data: dict):
    """Broadcast update to all connected WebSocket clients."""
    message = json.dumps(data)
    disconnected = []

    for ws in ws_connections:
        try:
            await ws.send_text(message)
        except:
            disconnected.append(ws)

    for ws in disconnected:
        ws_connections.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    ws_connections.append(websocket)
    logger.info("WebSocket client connected")

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Could handle client commands here
    except WebSocketDisconnect:
        ws_connections.remove(websocket)
        logger.info("WebSocket client disconnected")


# =============================================================================
# REST API Endpoints
# =============================================================================

@app.get("/api/agents")
async def get_agents():
    """Get list of all agents."""
    agents_list = []
    for name, agent in registered_agents.items():
        agents_list.append({
            "name": agent.get("name", name),
            "display_name": agent.get("display_name", name),
            "type": agent.get("type", "agent"),
            "version": agent.get("version", "1.0.0"),
            "capabilities": agent.get("capabilities", []),
            "status": agent.get("status", "offline"),
            "last_heartbeat": agent.get("last_heartbeat"),
        })
    return JSONResponse(agents_list)


@app.get("/api/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get agent details including passport."""
    if agent_name not in registered_agents:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    agent = registered_agents[agent_name]
    return JSONResponse({
        **agent,
        "messages": agent_messages.get(agent_name, [])[-50:],  # Last 50 messages
    })


def ensure_sender_connected():
    """Ensure bus_sender is connected, reconnect if needed."""
    global bus_sender

    needs_reconnect = False

    if bus_sender is None:
        needs_reconnect = True
    elif not bus_sender._connection:
        needs_reconnect = True
    elif bus_sender._connection.is_closed:
        needs_reconnect = True
    elif not bus_sender._channel:
        needs_reconnect = True
    elif bus_sender._channel.is_closed:
        needs_reconnect = True
    else:
        # Additional check: try to verify connection is actually alive
        try:
            # This will raise if connection is dead
            bus_sender._connection.process_data_events(time_limit=0)
        except Exception:
            needs_reconnect = True

    if needs_reconnect:
        logger.info("Reconnecting bus_sender...")
        try:
            # Close old connection if exists
            if bus_sender is not None:
                try:
                    bus_sender.disconnect()
                except Exception:
                    pass

            bus_sender = MindBus()
            bus_sender.connect()
            logger.info("bus_sender reconnected successfully")
        except Exception as e:
            logger.error(f"Failed to reconnect bus_sender: {e}")
            raise


@app.post("/api/agents/{agent_name}/command")
async def send_command(agent_name: str, command: dict):
    """Send COMMAND to agent."""
    if agent_name not in registered_agents:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    try:
        ensure_sender_connected()
    except Exception as e:
        return JSONResponse({"error": f"MindBus connection failed: {e}"}, status_code=503)

    action = command.get("action", "")
    params = command.get("params", {})

    if not action:
        return JSONResponse({"error": "Action is required"}, status_code=400)

    # Generate command ID
    command_id = str(uuid.uuid4())

    # Use fixed reply queue for all responses
    reply_to = MONITOR_REPLY_QUEUE

    # Store outgoing message in history
    outgoing_message = {
        "id": command_id,
        "type": "command",
        "from": "monitor",
        "to": agent_name,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "action": action,
            "params": params,
        }
    }

    if agent_name not in agent_messages:
        agent_messages[agent_name] = []
    agent_messages[agent_name].append(outgoing_message)

    # Send command via MindBus
    try:
        # Build routing key for agent: cmd.{role}.{agent_id}
        agent_type = registered_agents.get(agent_name, {}).get("type", "agent")
        target = f"{agent_type}.task"

        bus_sender.send_command(
            action=action,
            params=params,
            target=target,
            target_id=agent_name,
            source="monitor",
            reply_to=reply_to,
            context={"target_node": agent_name},  # For agent's target_node filtering
        )

        logger.info(f"Sent COMMAND to {agent_name}: {action}")

        # Set agent status to "working" while processing
        if agent_name in registered_agents:
            registered_agents[agent_name]["status"] = "working"
            # Broadcast status change to WebSocket clients
            asyncio.create_task(broadcast_update({
                "type": "agent_status",
                "agent": agent_name,
                "status": "working"
            }))

        return JSONResponse({
            "success": True,
            "command_id": command_id,
            "message": outgoing_message,
        })

    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/agents/{agent_name}/messages")
async def get_messages(agent_name: str, limit: int = 50):
    """Get message history for agent."""
    messages = agent_messages.get(agent_name, [])
    return JSONResponse(messages[-limit:])


# =============================================================================
# HTML Pages
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Main page - Agent Registry."""
    return get_index_html()


@app.get("/agent/{agent_name}", response_class=HTMLResponse)
async def agent_page(agent_name: str):
    """Agent detail page with chat interface."""
    if agent_name not in registered_agents:
        return HTMLResponse("<h1>Agent not found</h1>", status_code=404)
    return get_agent_html(agent_name)


def get_index_html() -> str:
    """Generate index page HTML."""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI_TEAM Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background: #fff;
            border-bottom: 1px solid #e0e0e0;
            padding: 15px 20px;
            margin-bottom: 20px;
        }
        header h1 {
            font-size: 1.5rem;
            font-weight: 500;
            color: #333;
        }
        header h1 span { color: #4a90a4; }
        .agents-table {
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #fafafa;
            font-weight: 500;
            color: #666;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        tr:hover { background: #f9f9f9; }
        tr { cursor: pointer; }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }
        .status-online { background: #5cb85c; }
        .status-offline { background: #999; }
        .status-working { background: #f0ad4e; animation: pulse 1.5s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .capabilities {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }
        .capability-tag {
            background: #e8f4f8;
            color: #4a90a4;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
    </style>
</head>
<body>
    <header>
        <h1><span>AI_TEAM</span> Monitor</h1>
    </header>

    <div class="container">
        <div class="agents-table">
            <table>
                <thead>
                    <tr>
                        <th style="width: 40px;"></th>
                        <th>Имя</th>
                        <th>Роль</th>
                        <th>Capabilities</th>
                        <th>Версия</th>
                    </tr>
                </thead>
                <tbody id="agents-body">
                    <tr><td colspan="5" class="empty-state">Загрузка...</td></tr>
                </tbody>
            </table>
        </div>
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
            const tbody = document.getElementById('agents-body');

            if (agents.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Нет зарегистрированных агентов</td></tr>';
                return;
            }

            tbody.innerHTML = agents.map(agent => `
                <tr onclick="window.location.href='/agent/${agent.name}'">
                    <td><span class="status-dot status-${agent.status}"></span></td>
                    <td><strong>${agent.display_name}</strong></td>
                    <td>${agent.type}</td>
                    <td>
                        <div class="capabilities">
                            ${agent.capabilities.slice(0, 3).map(c =>
                                `<span class="capability-tag">${c}</span>`
                            ).join('')}
                            ${agent.capabilities.length > 3 ?
                                `<span class="capability-tag">+${agent.capabilities.length - 3}</span>` : ''}
                        </div>
                    </td>
                    <td>${agent.version}</td>
                </tr>
            `).join('');
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

        // Refresh every 10 seconds
        setInterval(loadAgents, 10000);
    </script>
</body>
</html>"""


def get_agent_html(agent_name: str) -> str:
    """Generate agent detail page HTML."""
    agent = registered_agents.get(agent_name, {})
    display_name = agent.get("display_name", agent_name)
    capabilities = agent.get("capabilities", [])
    first_capability = capabilities[0] if capabilities else ""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name} - AI_TEAM Monitor</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.5;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        header {{
            background: #fff;
            border-bottom: 1px solid #e0e0e0;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        header a {{
            color: #4a90a4;
            text-decoration: none;
            font-size: 1.2rem;
        }}
        header h1 {{
            font-size: 1.2rem;
            font-weight: 500;
        }}
        .status-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }}
        .status-online {{ background: #5cb85c; }}
        .status-offline {{ background: #999; }}
        .status-working {{ background: #f0ad4e; animation: pulse 1.5s infinite; }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .main-content {{
            flex: 1;
            display: flex;
            overflow: hidden;
        }}
        .chat-area {{
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #fff;
        }}
        .messages {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}
        .message {{
            margin-bottom: 16px;
            max-width: 80%;
        }}
        .message.outgoing {{
            margin-left: auto;
        }}
        .message-header {{
            font-size: 0.75rem;
            color: #999;
            margin-bottom: 4px;
        }}
        .message-content {{
            padding: 10px 14px;
            border-radius: 12px;
            background: #f0f0f0;
        }}
        .message.outgoing .message-content {{
            background: #e3f2fd;
        }}
        .message.error .message-content {{
            background: #ffebee;
            color: #c62828;
        }}
        .message-text {{
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .message-meta {{
            font-size: 0.75rem;
            color: #999;
            margin-top: 6px;
        }}
        .input-area {{
            border-top: 1px solid #e0e0e0;
            padding: 16px;
            background: #fafafa;
        }}
        .input-row {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }}
        .input-row select {{
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            background: #fff;
            font-size: 0.95rem;
            min-width: 180px;
        }}
        .input-row input {{
            flex: 1;
            padding: 10px 14px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 0.95rem;
        }}
        .input-row input:focus, .input-row select:focus {{
            outline: none;
            border-color: #4a90a4;
        }}
        .input-row button {{
            padding: 10px 24px;
            background: #4a90a4;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 0.95rem;
            cursor: pointer;
        }}
        .input-row button:hover {{
            background: #3d7a8c;
        }}
        .input-row button:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .passport {{
            width: 280px;
            background: #fafafa;
            border-left: 1px solid #e0e0e0;
            padding: 20px;
            overflow-y: auto;
            font-size: 0.85rem;
        }}
        .passport h3 {{
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 12px;
            color: #666;
        }}
        .passport-section {{
            margin-bottom: 16px;
        }}
        .passport-section label {{
            display: block;
            color: #999;
            font-size: 0.75rem;
            margin-bottom: 2px;
        }}
        .passport-section .value {{
            color: #333;
        }}
        .capability-list {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .capability-item {{
            background: #e8f4f8;
            color: #4a90a4;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <header>
        <a href="/">&#8592;</a>
        <span class="status-dot status-offline" id="status-dot"></span>
        <h1 id="agent-title">{display_name}</h1>
    </header>

    <div class="main-content">
        <div class="chat-area">
            <div class="messages" id="messages"></div>

            <div class="input-area">
                <div class="input-row">
                    <select id="action-select">
                        {' '.join(f'<option value="{c}">{c}</option>' for c in capabilities) if capabilities else '<option value="">No capabilities</option>'}
                    </select>
                    <input type="text" id="param-input" placeholder="Введите параметр..." />
                    <button id="send-btn" onclick="sendCommand()">Отправить</button>
                </div>
            </div>
        </div>

        <div class="passport" id="passport">
            <h3>Паспорт агента</h3>
            <div id="passport-content">Загрузка...</div>
        </div>
    </div>

    <script>
        const agentName = '{agent_name}';
        let ws;

        async function loadAgent() {{
            try {{
                const response = await fetch(`/api/agents/${{agentName}}`);
                const agent = await response.json();

                // Update status
                const statusDot = document.getElementById('status-dot');
                statusDot.className = `status-dot status-${{agent.status}}`;

                // Update passport
                renderPassport(agent);

                // Render messages
                renderMessages(agent.messages || []);
            }} catch (e) {{
                console.error('Error loading agent:', e);
            }}
        }}

        function renderPassport(agent) {{
            const content = document.getElementById('passport-content');
            content.innerHTML = `
                <div class="passport-section">
                    <label>Name</label>
                    <div class="value">${{agent.name}}</div>
                </div>
                <div class="passport-section">
                    <label>Type</label>
                    <div class="value">${{agent.type}}</div>
                </div>
                <div class="passport-section">
                    <label>Version</label>
                    <div class="value">${{agent.version}}</div>
                </div>
                <div class="passport-section">
                    <label>Status</label>
                    <div class="value">${{agent.status}}</div>
                </div>
                <div class="passport-section">
                    <label>Capabilities</label>
                    <div class="capability-list">
                        ${{(agent.capabilities || []).map(c =>
                            `<div class="capability-item">${{c}}</div>`
                        ).join('')}}
                    </div>
                </div>
                <div class="passport-section">
                    <label>Tools</label>
                    <div class="capability-list">
                        ${{(agent.tools || []).map(t =>
                            `<div class="capability-item">${{t}}</div>`
                        ).join('')}}
                    </div>
                </div>
            `;
        }}

        function renderMessages(messages) {{
            const container = document.getElementById('messages');

            if (messages.length === 0) {{
                container.innerHTML = '<div style="text-align: center; color: #999; padding: 40px;">Нет сообщений</div>';
                return;
            }}

            container.innerHTML = messages.map(msg => {{
                const isOutgoing = msg.from === 'monitor';
                const isError = msg.type === 'error';

                let content = '';
                if (msg.type === 'command') {{
                    content = `<strong>${{msg.data.action}}</strong>`;
                    if (msg.data.params) {{
                        const params = Object.entries(msg.data.params)
                            .map(([k, v]) => `${{k}}: ${{v}}`)
                            .join(', ');
                        if (params) content += `<br/>${{params}}`;
                    }}
                }} else if (msg.type === 'result') {{
                    // Extract text from various possible locations in response
                    // Structure: MindBus.send_result() wraps agent output in {{status, output: <agent_result>}}
                    // Agent returns {{action, output: {{text: "..."}}}}
                    // Result: msg.data.output.output.text (double nested)
                    let text = '';
                    if (msg.data.output && msg.data.output.output && msg.data.output.output.text) {{
                        // Double-nested: MindBus wrapper + agent's output structure
                        text = msg.data.output.output.text;
                    }} else if (msg.data.output && msg.data.output.text) {{
                        // Single nested (fallback)
                        text = msg.data.output.text;
                    }} else if (msg.data.text) {{
                        text = msg.data.text;
                    }} else if (typeof msg.data.output === 'string') {{
                        text = msg.data.output;
                    }}

                    if (text) {{
                        // Show full text, no truncation
                        content = text;
                    }} else {{
                        // Fallback: show JSON but only essential fields
                        const summary = {{
                            action: msg.data.action,
                            status: msg.data.status
                        }};
                        content = JSON.stringify(summary, null, 2);
                    }}

                    // Add execution time if available
                    const execTime = msg.data.metrics?.execution_time_seconds ||
                                     msg.data.execution_time_ms ? (msg.data.execution_time_ms / 1000).toFixed(1) : null;
                    if (execTime) {{
                        content += `<div class="message-meta">${{execTime}}s</div>`;
                    }}
                }} else if (msg.type === 'error') {{
                    content = `<strong>Error:</strong> ${{msg.data.message || JSON.stringify(msg.data)}}`;
                }}

                return `
                    <div class="message ${{isOutgoing ? 'outgoing' : ''}} ${{isError ? 'error' : ''}}">
                        <div class="message-header">${{msg.from}} - ${{new Date(msg.timestamp).toLocaleTimeString()}}</div>
                        <div class="message-content">
                            <div class="message-text">${{content}}</div>
                        </div>
                    </div>
                `;
            }}).join('');

            // Auto-scroll only if user is already at bottom (within 100px tolerance)
            // This allows user to read earlier messages without being forced to bottom
            const isAtBottom = (container.scrollHeight - container.scrollTop - container.clientHeight) < 100;
            if (isAtBottom) {{
                container.scrollTop = container.scrollHeight;
            }}
        }}

        async function sendCommand() {{
            const actionSelect = document.getElementById('action-select');
            const paramInput = document.getElementById('param-input');
            const sendBtn = document.getElementById('send-btn');

            const action = actionSelect.value;
            const paramValue = paramInput.value.trim();

            if (!action) {{
                alert('Выберите action');
                return;
            }}

            // Build params based on action
            let params = {{}};
            if (action === 'write_article' || action === 'generate_outline') {{
                params.topic = paramValue || 'тестовая тема';
            }} else if (action === 'improve_text') {{
                params.text = paramValue || 'Тестовый текст для улучшения';
                params.feedback = 'Сделай текст более структурированным';
            }} else if (action === 'test.echo') {{
                params.message = paramValue || 'Hello from Monitor!';
            }} else if (action === 'generate_text') {{
                params.prompt = paramValue;
            }} else {{
                params.input = paramValue;
            }}

            sendBtn.disabled = true;

            try {{
                const response = await fetch(`/api/agents/${{agentName}}/command`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ action, params }})
                }});

                const result = await response.json();

                if (result.success) {{
                    paramInput.value = '';
                    loadAgent();  // Refresh to show new message
                }} else {{
                    alert('Error: ' + (result.error || 'Unknown error'));
                }}
            }} catch (e) {{
                alert('Error sending command: ' + e.message);
            }} finally {{
                sendBtn.disabled = false;
            }}
        }}

        function connectWebSocket() {{
            ws = new WebSocket(`ws://${{window.location.host}}/ws`);

            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.type === 'message' && data.agent === agentName) {{
                    loadAgent();  // Refresh messages
                }}
                if (data.type === 'agent_status' && data.agent === agentName) {{
                    loadAgent();  // Refresh status
                }}
            }};

            ws.onclose = () => {{
                setTimeout(connectWebSocket, 3000);
            }};
        }}

        // Handle Enter key
        document.getElementById('param-input').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') sendCommand();
        }});

        loadAgent();
        connectWebSocket();

        // Refresh every 5 seconds
        setInterval(loadAgent, 5000);
    </script>
</body>
</html>"""


# =============================================================================
# Application Lifecycle
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
# Main Entry Point
# =============================================================================

def main():
    """Run the Monitor web server."""
    print("\n" + "="*60)
    print("AI_TEAM Monitor")
    print("="*60)
    print("\nStarting web server...")
    print("Open http://localhost:8080 in your browser")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
