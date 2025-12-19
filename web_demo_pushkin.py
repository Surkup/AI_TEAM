#!/usr/bin/env python3
"""
AI_TEAM Web Demo — Writer Agent "Пушкин" Testing Interface.

Usage:
    1. Make sure Docker/RabbitMQ is running
    2. Run: ./venv/bin/python web_demo_pushkin.py
    3. Open: http://localhost:8080

This demo allows you to test WriterAgent "Пушкин" with different actions:
- write_article: Write an article on any topic
- improve_text: Improve existing text based on feedback
- generate_outline: Create an article outline/structure
"""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from mindbus.core import MindBus
from agents.writer_agent import WriterAgent
from registry import NodeRegistry, RegistryService

# Global state
agent = None
result_listener = None
registry_service = None
pending_requests = {}
pending_lock = threading.Lock()

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI_TEAM — Пушкин (Writer Agent)</title>
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
            max-width: 900px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 5px;
            font-size: 2.2em;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 25px;
        }
        .agent-card {
            background: linear-gradient(135deg, #0f3460 0%, #1a1a4e 100%);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #333;
        }
        .agent-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        .agent-avatar {
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin-right: 15px;
        }
        .agent-info h2 {
            color: #ffd700;
            margin-bottom: 5px;
        }
        .agent-info p {
            color: #888;
            font-size: 14px;
        }
        .capabilities {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .capability {
            background: #1a1a2e;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            color: #00ff88;
            border: 1px solid #00ff88;
        }
        .status-bar {
            background: #0a0a15;
            border-radius: 8px;
            padding: 10px 15px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
            font-size: 13px;
        }
        .status-item {
            display: flex;
            align-items: center;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-dot.green { background: #00ff88; }
        .input-section {
            background: #0f3460;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .action-selector {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        .action-btn {
            flex: 1;
            padding: 12px;
            background: #1a1a2e;
            border: 2px solid #333;
            border-radius: 8px;
            color: #888;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }
        .action-btn:hover {
            border-color: #ffd700;
            color: #ffd700;
        }
        .action-btn.active {
            border-color: #ffd700;
            background: rgba(255, 215, 0, 0.1);
            color: #ffd700;
        }
        .input-group {
            margin-bottom: 15px;
        }
        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #888;
            font-size: 14px;
        }
        textarea, input[type="text"], select {
            width: 100%;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            color: #eee;
            padding: 12px;
            font-size: 15px;
        }
        textarea {
            min-height: 100px;
            resize: vertical;
        }
        textarea:focus, input:focus, select:focus {
            outline: none;
            border-color: #ffd700;
        }
        .params-row {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 15px;
        }
        button.send-btn {
            width: 100%;
            background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%);
            border: none;
            border-radius: 8px;
            color: #1a1a2e;
            padding: 14px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button.send-btn:hover {
            transform: scale(1.01);
        }
        button.send-btn:disabled {
            background: #555;
            cursor: not-allowed;
            transform: none;
        }
        .response-section {
            background: #0f3460;
            border-radius: 12px;
            padding: 20px;
        }
        .response-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .response-content {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 20px;
            min-height: 150px;
            white-space: pre-wrap;
            line-height: 1.7;
            font-size: 15px;
        }
        .metrics-bar {
            margin-top: 15px;
            padding: 12px;
            background: #0a0a15;
            border-radius: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            font-size: 13px;
            color: #888;
        }
        .metric {
            display: flex;
            align-items: center;
        }
        .metric-label {
            color: #555;
            margin-right: 5px;
        }
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 150px;
            color: #888;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid #333;
            border-top-color: #ffd700;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 15px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .improve-section {
            display: none;
        }
        .improve-section.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>AI_TEAM Demo</h1>
        <p class="subtitle">Writer Agent Testing Interface</p>

        <div class="agent-card">
            <div class="agent-header">
                <div class="agent-avatar">P</div>
                <div class="agent-info">
                    <h2>Пушкин</h2>
                    <p>AI-копирайтер, специализирующийся на создании текстового контента</p>
                </div>
            </div>
            <div class="capabilities">
                <span class="capability">write_article</span>
                <span class="capability">improve_text</span>
                <span class="capability">generate_outline</span>
            </div>
        </div>

        <div class="status-bar">
            <div class="status-item">
                <div class="status-dot green"></div>
                <span>MindBus</span>
            </div>
            <div class="status-item">
                <div class="status-dot green"></div>
                <span>Registry</span>
            </div>
            <div class="status-item">
                <div class="status-dot green"></div>
                <span>Пушкин Online</span>
            </div>
        </div>

        <div class="input-section">
            <div class="action-selector">
                <button class="action-btn active" onclick="selectAction('write_article')">
                    Написать статью
                </button>
                <button class="action-btn" onclick="selectAction('improve_text')">
                    Улучшить текст
                </button>
                <button class="action-btn" onclick="selectAction('generate_outline')">
                    Создать структуру
                </button>
            </div>

            <!-- Write Article Form -->
            <div id="form-write_article" class="action-form">
                <div class="input-group">
                    <label>Тема статьи</label>
                    <input type="text" id="topic" placeholder="Например: Искусственный интеллект в медицине">
                </div>
                <div class="params-row">
                    <div class="input-group">
                        <label>Стиль</label>
                        <select id="style">
                            <option value="formal">Формальный</option>
                            <option value="casual">Разговорный</option>
                            <option value="technical">Технический</option>
                            <option value="creative">Творческий</option>
                        </select>
                    </div>
                    <div class="input-group">
                        <label>Объём (слов)</label>
                        <select id="length">
                            <option value="300">~300 слов</option>
                            <option value="500" selected>~500 слов</option>
                            <option value="1000">~1000 слов</option>
                            <option value="1500">~1500 слов</option>
                        </select>
                    </div>
                    <div class="input-group">
                        <label>Язык</label>
                        <select id="language">
                            <option value="ru" selected>Русский</option>
                            <option value="en">English</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Improve Text Form -->
            <div id="form-improve_text" class="action-form" style="display: none;">
                <div class="input-group">
                    <label>Текст для улучшения</label>
                    <textarea id="text_to_improve" rows="5" placeholder="Вставьте текст, который нужно улучшить..."></textarea>
                </div>
                <div class="input-group">
                    <label>Что улучшить? (обратная связь)</label>
                    <input type="text" id="feedback" placeholder="Например: Сделай текст более живым и добавь примеры">
                </div>
            </div>

            <!-- Generate Outline Form -->
            <div id="form-generate_outline" class="action-form" style="display: none;">
                <div class="input-group">
                    <label>Тема для структуры</label>
                    <input type="text" id="outline_topic" placeholder="Например: Как начать бизнес с нуля">
                </div>
                <div class="input-group">
                    <label>Количество разделов</label>
                    <select id="sections_count">
                        <option value="3">3 раздела</option>
                        <option value="5" selected>5 разделов</option>
                        <option value="7">7 разделов</option>
                    </select>
                </div>
            </div>

            <button class="send-btn" id="sendBtn" onclick="sendRequest()">
                Отправить Пушкину
            </button>
        </div>

        <div class="response-section">
            <div class="response-header">
                <h3>Ответ Пушкина</h3>
                <span id="responseTime"></span>
            </div>
            <div id="responseContent" class="response-content">
                Здесь появится результат работы агента...
            </div>
            <div id="metricsBar" class="metrics-bar" style="display: none;">
                <div class="metric">
                    <span class="metric-label">Модель:</span>
                    <span id="metricModel">-</span>
                </div>
                <div class="metric">
                    <span class="metric-label">LLM вызовов:</span>
                    <span id="metricCalls">-</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Итераций:</span>
                    <span id="metricIterations">-</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Слов:</span>
                    <span id="metricWords">-</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Время:</span>
                    <span id="metricTime">-</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentAction = 'write_article';

        function selectAction(action) {
            currentAction = action;

            // Update buttons
            document.querySelectorAll('.action-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');

            // Show/hide forms
            document.querySelectorAll('.action-form').forEach(form => {
                form.style.display = 'none';
            });
            document.getElementById('form-' + action).style.display = 'block';

            // Update button text
            const btnTexts = {
                'write_article': 'Написать статью',
                'improve_text': 'Улучшить текст',
                'generate_outline': 'Создать структуру'
            };
            document.getElementById('sendBtn').textContent = btnTexts[action];
        }

        function getParams() {
            if (currentAction === 'write_article') {
                return {
                    topic: document.getElementById('topic').value,
                    style: document.getElementById('style').value,
                    length: parseInt(document.getElementById('length').value),
                    language: document.getElementById('language').value
                };
            } else if (currentAction === 'improve_text') {
                return {
                    text: document.getElementById('text_to_improve').value,
                    feedback: document.getElementById('feedback').value
                };
            } else if (currentAction === 'generate_outline') {
                return {
                    topic: document.getElementById('outline_topic').value,
                    sections_count: parseInt(document.getElementById('sections_count').value)
                };
            }
            return {};
        }

        async function sendRequest() {
            const params = getParams();
            const btn = document.getElementById('sendBtn');
            const content = document.getElementById('responseContent');
            const metricsBar = document.getElementById('metricsBar');
            const timeEl = document.getElementById('responseTime');

            // Validate input
            if (currentAction === 'write_article' && !params.topic) {
                alert('Пожалуйста, введите тему статьи');
                return;
            }
            if (currentAction === 'improve_text' && !params.text) {
                alert('Пожалуйста, введите текст для улучшения');
                return;
            }
            if (currentAction === 'generate_outline' && !params.topic) {
                alert('Пожалуйста, введите тему');
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Пушкин работает...';
            content.innerHTML = '<div class="loading"><div class="spinner"></div><span>Пушкин обрабатывает запрос через MindBus...</span></div>';
            metricsBar.style.display = 'none';

            const startTime = Date.now();

            try {
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: currentAction,
                        params: params
                    })
                });

                const data = await response.json();
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

                if (data.error) {
                    content.textContent = 'Ошибка: ' + data.error;
                    content.style.color = '#ff4444';
                } else {
                    // Format text (simple markdown rendering)
                    let text = data.text || data.output?.text || 'Нет текста';
                    text = text.replace(/^## /gm, '\\n## ');
                    text = text.replace(/^### /gm, '\\n### ');
                    content.textContent = text;
                    content.style.color = '#eee';

                    timeEl.textContent = elapsed + 's';

                    // Show metrics
                    if (data.metrics) {
                        document.getElementById('metricModel').textContent = data.metrics.model || '-';
                        document.getElementById('metricCalls').textContent = data.metrics.llm_calls || '-';
                        document.getElementById('metricIterations').textContent = data.metrics.iterations || '-';
                        document.getElementById('metricTime').textContent = (data.metrics.execution_time_seconds || elapsed) + 's';
                    }
                    if (data.output?.word_count) {
                        document.getElementById('metricWords').textContent = data.output.word_count;
                    }
                    metricsBar.style.display = 'flex';
                }
            } catch (e) {
                content.textContent = 'Ошибка: ' + e.message;
                content.style.color = '#ff4444';
            }

            btn.disabled = false;
            const btnTexts = {
                'write_article': 'Написать статью',
                'improve_text': 'Улучшить текст',
                'generate_outline': 'Создать структуру'
            };
            btn.textContent = btnTexts[currentAction];
        }
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
        if self.path == "/api/execute":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body)
                action = data.get("action", "write_article")
                params = data.get("params", {})

                if not params:
                    self.send_json({"error": "No parameters provided"})
                    return

                # Send command through MindBus and wait for result
                result = send_command_and_wait(action, params)
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
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def get_registered_nodes():
    """Get list of registered nodes."""
    global registry_service

    if registry_service is None:
        return {"nodes": [], "error": "Registry not initialized"}

    try:
        registry = registry_service.get_registry()
        nodes = registry.get_all_nodes()

        result = []
        for passport in nodes:
            entry = registry._nodes.get(passport.metadata.uid)
            health = entry.health_state.value if entry else "UNKNOWN"

            result.append({
                "name": passport.metadata.name,
                "type": passport.metadata.node_type.value,
                "capabilities": [cap.name for cap in passport.spec.capabilities],
                "health": health,
            })

        return {"nodes": result}

    except Exception as e:
        return {"nodes": [], "error": str(e)}


def on_result_received(event, data):
    """Callback for RESULT messages."""
    corr_id = event.get("correlationid")

    with pending_lock:
        if corr_id in pending_requests:
            pending_requests[corr_id]["result"] = {
                "data": data,
                "event": event
            }
            pending_requests[corr_id]["event"].set()


def on_error_received(event, data):
    """Callback for ERROR messages."""
    corr_id = event.get("correlationid")

    with pending_lock:
        if corr_id in pending_requests:
            pending_requests[corr_id]["result"] = {
                "error": data.get("error", {}),
                "event": event
            }
            pending_requests[corr_id]["event"].set()


def send_command_and_wait(action: str, params: dict, timeout: float = 120.0) -> dict:
    """Send command to WriterAgent via MindBus and wait for response.

    Uses RPC reply-to pattern: COMMAND includes reply_to queue name,
    agent sends RESULT/ERROR directly to that queue.
    """

    wait_event = threading.Event()

    # Generate unique reply queue name for this request
    import uuid
    reply_queue = f"demo.reply.{uuid.uuid4().hex[:8]}"

    sender = MindBus()
    sender.connect()

    # Declare reply queue for RPC response
    sender._channel.queue_declare(queue=reply_queue, durable=False, auto_delete=True)

    # Set up callback for response on reply queue
    def on_rpc_response(ch, method, properties, body):
        from cloudevents.http import from_json
        try:
            event = from_json(body)
            data = event.data
            event_dict = {
                "id": event["id"],
                "type": event["type"],
                "source": event["source"],
                "correlationid": properties.correlation_id,
            }

            # Check if this is our response
            if properties.correlation_id:
                with pending_lock:
                    if properties.correlation_id in pending_requests:
                        if "error" in data:
                            pending_requests[properties.correlation_id]["result"] = {
                                "error": data.get("error", {}),
                                "event": event_dict
                            }
                        else:
                            pending_requests[properties.correlation_id]["result"] = {
                                "data": data,
                                "event": event_dict
                            }
                        pending_requests[properties.correlation_id]["event"].set()

            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"   Error processing RPC response: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    # Subscribe to reply queue
    sender._channel.basic_consume(queue=reply_queue, on_message_callback=on_rpc_response)

    # Send command to writer agent with reply_to queue
    command_id = sender.send_command(
        action=action,
        params=params,
        target="agent_writer_001",  # WriterAgent routing key
        source="web-demo-pushkin",
        subject=f"pushkin-{action}",
        timeout_seconds=120,
        reply_to=reply_queue,  # Agent will send RESULT/ERROR here
    )

    print(f"   -> COMMAND sent: {action} (id: {command_id[:8]}..., reply_to: {reply_queue})")

    with pending_lock:
        pending_requests[command_id] = {
            "event": wait_event,
            "result": None
        }

    # Start consuming with timeout
    def consume_with_timeout():
        try:
            # Process messages until we get response or timeout
            start = time.time()
            while time.time() - start < timeout:
                sender._connection.process_data_events(time_limit=1.0)
                with pending_lock:
                    if command_id in pending_requests and pending_requests[command_id]["result"] is not None:
                        break
        except Exception as e:
            print(f"   Consume error: {e}")

    consume_with_timeout()
    sender.disconnect()

    with pending_lock:
        request_data = pending_requests.pop(command_id, None)

    if request_data is None or request_data["result"] is None:
        return {"error": "Timeout waiting for response from Пушкин"}

    result = request_data["result"]

    if "error" in result:
        return {"error": result["error"].get("message", "Unknown error")}

    data = result["data"]
    output = data.get("output", {})

    # SSOT ResultData: data.output contains agent's full result
    # WriterAgent result structure: {action, status, output: {text, word_count}, metrics, agent}
    # So actual text is in: data.output.output.text
    inner_output = output.get("output", {})
    text = inner_output.get("text", "") if isinstance(inner_output, dict) else ""

    return {
        "text": text,
        "output": inner_output,  # The actual output dict with text, word_count, etc.
        "metrics": output.get("metrics", data.get("metrics", {})),  # Try both places
        "agent": output.get("agent", data.get("agent", {}))
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


def start_registry_service():
    """Start the Registry Service."""
    global registry_service

    print("   Starting Registry Service...")

    try:
        registry_service = RegistryService()
        registry_service.bus.connect()

        registry_service.bus.subscribe("evt.node.registered", registry_service._on_node_registered)
        registry_service.bus.subscribe("evt.node.heartbeat", registry_service._on_node_heartbeat)
        registry_service.bus.subscribe("evt.node.deregistered", registry_service._on_node_deregistered)

        registry_service.registry.start_cleanup_thread()

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
    """Start result listener.

    NOTE: With RPC reply-to pattern, each request creates its own reply queue,
    so this global listener is no longer needed for RESULT/ERROR messages.
    Kept for backwards compatibility and potential event monitoring.
    """
    global result_listener

    print("   Result Listener skipped (using RPC reply-to pattern)")
    return True


def start_writer_agent():
    """Start WriterAgent 'Пушкин'."""
    global agent

    print("   Starting WriterAgent 'Пушкин'...")

    try:
        agent = WriterAgent()
        agent.bus.connect()

        # Subscribe to commands for writer agent
        agent.bus.subscribe("cmd.agent_writer_001.*", agent._on_command)
        agent.bus.subscribe("cmd.writer.*", agent._on_command)

        # Register with Node Registry (without heartbeat to avoid pika threading issues)
        # NOTE: Heartbeat thread uses same MindBus connection which causes pika buffer issues
        # For production, need separate connection for heartbeats
        # if agent._enable_registration:
        #     agent._send_registration_event()
        #     agent._start_heartbeat_thread()
        print(f"   Пушкин ready (heartbeat disabled for demo stability)")

        agent_thread = threading.Thread(
            target=agent.bus.start_consuming,
            daemon=True
        )
        agent_thread.start()

        print(f"   Пушкин ready (model: {agent.llm_model})")
        return True

    except Exception as e:
        print(f"   Failed to start Пушкин: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("\n" + "=" * 55)
    print("   AI_TEAM — Writer Agent 'Пушкин' Demo")
    print("=" * 55)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n   ERROR: No OpenAI API key found!")
        print("   Please add your key to .env file")
        return

    print("\n1. Checking RabbitMQ...")
    if not check_rabbitmq():
        print("   ERROR: RabbitMQ is not running!")
        print("   Start it with: docker start rabbitmq")
        return
    print("   RabbitMQ OK")

    print("\n2. Starting services...")

    if not start_registry_service():
        return

    time.sleep(0.3)

    if not start_result_listener():
        return

    time.sleep(0.3)

    if not start_writer_agent():
        return

    time.sleep(0.5)

    # Start web server
    print("\n3. Starting web server...")

    PORT = 8080

    with socketserver.TCPServer(("", PORT), DemoHandler) as httpd:
        print(f"\n" + "=" * 55)
        print(f"   Open in browser: http://localhost:{PORT}")
        print(f"=" * 55)
        print("\n   Press Ctrl+C to stop\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n   Shutting down Пушкин...")


if __name__ == "__main__":
    main()
