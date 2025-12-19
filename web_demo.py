#!/usr/bin/env python3
"""
AI_TEAM Web Demo — Simple web interface for testing MindBus system.

Usage:
    1. Make sure Docker is running (for RabbitMQ)
    2. Run: ./venv/bin/python web_demo.py
    3. Open: http://localhost:8080

This script automatically:
- Starts RabbitMQ (if not running)
- Starts SimpleAIAgent in background
- Starts a permanent result listener
- Provides web UI to send prompts and see responses through MindBus
"""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from mindbus.core import MindBus
from agents.simple_ai_agent import SimpleAIAgent
from registry import NodeRegistry, RegistryService

# Global state
agent = None
result_listener = None
registry_service = None
pending_requests = {}  # command_id -> {"event": threading.Event, "result": None}
pending_lock = threading.Lock()

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI_TEAM Demo</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 10px;
            font-size: 2em;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 30px;
        }
        .status {
            background: #0f3460;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .status-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .status-dot.green { background: #00ff88; }
        .status-dot.yellow { background: #ffcc00; }
        .status-dot.red { background: #ff4444; }
        .input-section {
            background: #0f3460;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        textarea {
            width: 100%;
            height: 100px;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            color: #eee;
            padding: 15px;
            font-size: 16px;
            resize: vertical;
            margin-bottom: 15px;
        }
        textarea:focus {
            outline: none;
            border-color: #00ff88;
        }
        button {
            background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
            border: none;
            border-radius: 8px;
            color: #1a1a2e;
            padding: 12px 30px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: scale(1.02);
        }
        button:disabled {
            background: #555;
            cursor: not-allowed;
            transform: none;
        }
        .response-section {
            background: #0f3460;
            border-radius: 10px;
            padding: 20px;
        }
        .response-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        .response-content {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 20px;
            min-height: 100px;
            white-space: pre-wrap;
            line-height: 1.6;
        }
        .metrics {
            margin-top: 15px;
            padding: 10px;
            background: #1a1a2e;
            border-radius: 8px;
            font-size: 14px;
            color: #888;
        }
        .metrics span {
            margin-right: 20px;
        }
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100px;
        }
        .spinner {
            width: 30px;
            height: 30px;
            border: 3px solid #333;
            border-top-color: #00ff88;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .message-flow {
            background: #0a0a15;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            font-family: monospace;
            font-size: 13px;
        }
        .flow-step {
            padding: 5px 0;
            display: flex;
            align-items: center;
        }
        .flow-step.command { color: #4a9eff; }
        .flow-step.result { color: #00ff88; }
        .flow-step.error { color: #ff4444; }
        .flow-arrow {
            margin: 0 10px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>AI_TEAM Demo</h1>
        <p class="subtitle">MindBus + SimpleAIAgent + OpenAI</p>

        <div class="status">
            <div class="status-item">
                <div class="status-dot green"></div>
                <span>RabbitMQ (MindBus)</span>
            </div>
            <div class="status-item">
                <div class="status-dot green"></div>
                <span>Node Registry</span>
            </div>
            <div class="status-item">
                <div class="status-dot green"></div>
                <span>Result Listener</span>
            </div>
        </div>

        <div class="nodes-section" style="background: #0f3460; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
            <h3 style="margin-bottom: 10px;">Registered Nodes</h3>
            <div id="nodesList" style="font-size: 14px; color: #888;">
                Loading...
            </div>
        </div>

        <div class="input-section">
            <textarea id="prompt" placeholder="Enter your prompt here...">Write a haiku about programming</textarea>
            <button id="sendBtn" onclick="sendPrompt()">Send to AI Agent</button>
        </div>

        <div class="response-section">
            <div class="response-header">
                <h3>Response</h3>
                <span id="responseTime"></span>
            </div>
            <div id="responseContent" class="response-content">
                Response will appear here...
            </div>
            <div id="metrics" class="metrics" style="display: none;">
                <span id="metricModel"></span>
                <span id="metricTokens"></span>
                <span id="metricCost"></span>
            </div>
            <div id="messageFlow" class="message-flow" style="display: none;">
                <div class="flow-step command">COMMAND: Web UI -> MindBus -> SimpleAIAgent</div>
                <div class="flow-step result">RESULT: SimpleAIAgent -> MindBus -> Web UI</div>
            </div>
        </div>
    </div>

    <script>
        async function sendPrompt() {
            const prompt = document.getElementById('prompt').value;
            const btn = document.getElementById('sendBtn');
            const content = document.getElementById('responseContent');
            const metrics = document.getElementById('metrics');
            const flow = document.getElementById('messageFlow');
            const timeEl = document.getElementById('responseTime');

            btn.disabled = true;
            btn.textContent = 'Sending via MindBus...';
            content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            metrics.style.display = 'none';
            flow.style.display = 'none';

            const startTime = Date.now();

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: prompt })
                });

                const data = await response.json();
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

                if (data.error) {
                    content.textContent = 'Error: ' + data.error;
                    content.style.color = '#ff4444';
                } else {
                    content.textContent = data.text;
                    content.style.color = '#eee';

                    timeEl.textContent = elapsed + 's';

                    if (data.metrics) {
                        document.getElementById('metricModel').textContent = 'Model: ' + data.metrics.model;
                        document.getElementById('metricTokens').textContent = 'Tokens: ' + data.metrics.tokens_total;
                        document.getElementById('metricCost').textContent = 'Cost: $' + data.metrics.cost_usd.toFixed(6);
                        metrics.style.display = 'block';
                    }

                    flow.style.display = 'block';
                }
            } catch (e) {
                content.textContent = 'Error: ' + e.message;
                content.style.color = '#ff4444';
            }

            btn.disabled = false;
            btn.textContent = 'Send to AI Agent';
        }

        async function loadNodes() {
            try {
                const response = await fetch('/api/nodes');
                const data = await response.json();
                const nodesList = document.getElementById('nodesList');

                if (data.nodes && data.nodes.length > 0) {
                    let html = '';
                    for (const node of data.nodes) {
                        const statusColor = node.health === 'ALIVE' ? '#00ff88' : '#ffcc00';
                        html += `<div style="display: flex; align-items: center; padding: 5px 0; border-bottom: 1px solid #333;">
                            <div style="width: 8px; height: 8px; border-radius: 50%; background: ${statusColor}; margin-right: 10px;"></div>
                            <span style="color: #eee; min-width: 150px;">${node.name}</span>
                            <span style="color: #888; min-width: 80px;">${node.type}</span>
                            <span style="color: #666; font-size: 12px;">${node.capabilities.join(', ')}</span>
                        </div>`;
                    }
                    nodesList.innerHTML = html;
                } else {
                    nodesList.innerHTML = '<span style="color: #666;">No nodes registered yet</span>';
                }
            } catch (e) {
                document.getElementById('nodesList').innerHTML = '<span style="color: #ff4444;">Error loading nodes</span>';
            }
        }

        // Load nodes on page load and refresh every 5 seconds
        loadNodes();
        setInterval(loadNodes, 5000);
    </script>
</body>
</html>
"""


class DemoHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for the demo."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/api/nodes":
            self.send_json(get_registered_nodes())
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/api/generate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body)
                prompt = data.get("prompt", "")

                if not prompt:
                    self.send_json({"error": "No prompt provided"})
                    return

                # Send command through MindBus and wait for result
                result = send_command_and_wait(prompt)
                self.send_json(result)

            except Exception as e:
                self.send_json({"error": str(e)})
        else:
            self.send_error(404)

    def send_json(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def get_registered_nodes():
    """Get list of registered nodes for API."""
    global registry_service

    if registry_service is None:
        return {"nodes": [], "error": "Registry not initialized"}

    try:
        registry = registry_service.get_registry()
        nodes = registry.get_all_nodes()

        result = []
        for passport in nodes:
            # Get health state from registry entry
            entry = registry._nodes.get(passport.metadata.uid)
            health = entry.health_state.value if entry else "UNKNOWN"

            result.append({
                "name": passport.metadata.name,
                "type": passport.metadata.node_type.value,
                "uid": passport.metadata.uid[:8] + "...",
                "capabilities": [cap.name for cap in passport.spec.capabilities],
                "health": health,
                "phase": passport.status.phase.value,
            })

        return {"nodes": result, "total": len(result)}

    except Exception as e:
        return {"nodes": [], "error": str(e)}


def on_result_received(event, data):
    """Global callback for all RESULT messages."""
    corr_id = event.get("correlationid")

    with pending_lock:
        if corr_id in pending_requests:
            pending_requests[corr_id]["result"] = {
                "data": data,
                "event": event
            }
            pending_requests[corr_id]["event"].set()


def on_error_received(event, data):
    """Global callback for all ERROR messages."""
    corr_id = event.get("correlationid")

    with pending_lock:
        if corr_id in pending_requests:
            pending_requests[corr_id]["result"] = {
                "error": data.get("error", {}),
                "event": event
            }
            pending_requests[corr_id]["event"].set()


def send_command_and_wait(prompt: str, timeout: float = 60.0) -> dict:
    """Send prompt via MindBus and wait for response."""

    # Create event to wait for response
    wait_event = threading.Event()

    # Send command
    sender = MindBus()
    sender.connect()

    command_id = sender.send_command(
        action="generate_text",
        params={"prompt": prompt, "max_tokens": 500},
        target="simple_ai_agent",
        source="web-demo",
        subject="web-request",
        timeout_seconds=60
    )

    # Register this request
    with pending_lock:
        pending_requests[command_id] = {
            "event": wait_event,
            "result": None
        }

    sender.disconnect()

    # Wait for result
    wait_event.wait(timeout=timeout)

    # Get result
    with pending_lock:
        request_data = pending_requests.pop(command_id, None)

    if request_data is None or request_data["result"] is None:
        return {"error": "Timeout waiting for response"}

    result = request_data["result"]

    if "error" in result:
        return {"error": result["error"].get("message", "Unknown error")}

    output = result["data"].get("output", {})
    return {
        "text": output.get("text", "No text generated"),
        "metrics": output.get("metrics", {})
    }


def check_rabbitmq():
    """Check if RabbitMQ is running."""
    try:
        bus = MindBus()
        bus.connect()
        bus.disconnect()
        return True
    except:
        return False


def start_rabbitmq():
    """Start RabbitMQ container if not running."""
    print("   Checking RabbitMQ...")

    # Check if container exists
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=rabbitmq", "--format", "{{.Status}}"],
        capture_output=True, text=True
    )

    if "Up" in result.stdout:
        print("   RabbitMQ is already running")
        return True

    if result.stdout.strip():
        # Container exists but not running
        print("   Starting existing RabbitMQ container...")
        subprocess.run(["docker", "start", "rabbitmq"], capture_output=True)
    else:
        # Container doesn't exist
        print("   Creating RabbitMQ container...")
        subprocess.run([
            "docker", "run", "-d", "--name", "rabbitmq",
            "-p", "5672:5672", "-p", "15672:15672",
            "rabbitmq:3-management"
        ], capture_output=True)

    # Wait for RabbitMQ to be ready
    print("   Waiting for RabbitMQ to start...")
    for i in range(30):
        if check_rabbitmq():
            print("   RabbitMQ is ready")
            return True
        time.sleep(1)

    print("   Failed to start RabbitMQ!")
    return False


def start_registry_service():
    """Start the Registry Service in background."""
    global registry_service

    print("   Starting Registry Service...")

    try:
        registry_service = RegistryService()
        registry_service.bus.connect()

        # Subscribe to node events
        registry_service.bus.subscribe("evt.node.registered", registry_service._on_node_registered)
        registry_service.bus.subscribe("evt.node.heartbeat", registry_service._on_node_heartbeat)
        registry_service.bus.subscribe("evt.node.deregistered", registry_service._on_node_deregistered)

        # Start cleanup thread
        registry_service.registry.start_cleanup_thread()

        # Start consuming in background
        registry_thread = threading.Thread(
            target=registry_service.bus.start_consuming,
            daemon=True
        )
        registry_thread.start()

        print("   Registry Service ready")
        return True

    except Exception as e:
        print(f"   Failed to start Registry Service: {e}")
        return False


def start_result_listener():
    """Start a permanent listener for results."""
    global result_listener

    print("   Starting Result Listener...")

    result_listener = MindBus()
    result_listener.connect()
    result_listener.subscribe("result.#", on_result_received)
    result_listener.subscribe("error.#", on_error_received)

    listener_thread = threading.Thread(
        target=result_listener.start_consuming,
        daemon=True
    )
    listener_thread.start()

    print("   Result Listener ready")
    return True


def start_agent():
    """Start SimpleAIAgent in background."""
    global agent

    print("   Starting SimpleAIAgent...")

    try:
        agent = SimpleAIAgent()
        agent.bus.connect()
        agent.bus.subscribe("cmd.simple_ai_agent.*", agent._on_command)
        agent.bus.subscribe("cmd.ai_agent.*", agent._on_command)

        # Send registration event to Registry Service
        if agent._enable_registration:
            agent._send_registration_event()
            agent._start_heartbeat_thread()
            print(f"   SimpleAIAgent registered with Node Registry")

        agent_thread = threading.Thread(
            target=agent.bus.start_consuming,
            daemon=True
        )
        agent_thread.start()

        print(f"   SimpleAIAgent ready (model: {agent.model})")
        return True

    except Exception as e:
        print(f"   Failed to start agent: {e}")
        return False


def main():
    """Main entry point."""
    print("\n" + "=" * 50)
    print("   AI_TEAM Web Demo")
    print("=" * 50)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your"):
        print("\n   ERROR: No OpenAI API key found!")
        print("   Please add your key to .env file")
        return

    print("\n1. Starting services...")

    # Start RabbitMQ
    if not start_rabbitmq():
        print("\n   ERROR: Could not start RabbitMQ")
        print("   Make sure Docker is running")
        return

    # Start Registry Service FIRST
    if not start_registry_service():
        print("\n   ERROR: Could not start Registry Service")
        return

    # Give registry time to subscribe
    time.sleep(0.3)

    # Start Result Listener
    if not start_result_listener():
        print("\n   ERROR: Could not start result listener")
        return

    # Give listener time to subscribe
    time.sleep(0.3)

    # Start Agent (it will register itself with Registry)
    if not start_agent():
        return

    # Give agent time to subscribe
    time.sleep(0.5)

    # Start web server
    print("\n2. Starting web server...")

    PORT = 8080

    with socketserver.TCPServer(("", PORT), DemoHandler) as httpd:
        print(f"\n" + "=" * 50)
        print(f"   Open in browser: http://localhost:{PORT}")
        print(f"=" * 50)
        print("\n   Press Ctrl+C to stop\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n   Shutting down...")


if __name__ == "__main__":
    main()
