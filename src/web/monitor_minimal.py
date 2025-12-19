"""
Minimal Monitor for Docker debugging - NO MindBus connection.
This tests if the issue is in FastAPI/uvicorn or MindBus.
"""

import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Minimal Monitor Test", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Simple test page."""
    return """<!DOCTYPE html>
<html>
<head><title>Minimal Monitor Test</title></head>
<body>
    <h1>Minimal Monitor Test</h1>
    <p>If you see this page, FastAPI/uvicorn is working fine.</p>
    <p>No MindBus/RabbitMQ connections in this test.</p>
</body>
</html>"""


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


@app.on_event("startup")
async def startup():
    logger.info("Minimal Monitor started - NO MindBus connections")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MINIMAL MONITOR TEST - No MindBus")
    print("="*60)
    print("\nStarting minimal web server...")
    print("Open http://localhost:8080 in your browser")
    print("Press Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
