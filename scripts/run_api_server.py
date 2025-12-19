#!/usr/bin/env python3
"""
Run API Gateway Server.

Usage:
    ./venv/bin/python scripts/run_api_server.py

Then test with:
    curl http://localhost:8000/status
    curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"description": "Write a poem"}'
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn
from api_gateway.gateway import create_app


def main():
    """Run the API server."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )

    print("\n" + "=" * 60)
    print("   🚀 AI_TEAM API Gateway")
    print("=" * 60)
    print("\n   Starting server at http://localhost:8000")
    print("\n   Endpoints:")
    print("   - GET  /          - API info")
    print("   - GET  /status    - System status")
    print("   - GET  /cards     - List process cards")
    print("   - POST /tasks     - Create task")
    print("   - GET  /tasks     - List tasks")
    print("   - GET  /tasks/:id - Get task")
    print("   - POST /process   - Execute process card")
    print("\n   Example:")
    print('   curl -X POST http://localhost:8000/tasks \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"description": "Write a haiku"}\'')
    print("\n" + "=" * 60)
    print("   Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    # Create and run app
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
