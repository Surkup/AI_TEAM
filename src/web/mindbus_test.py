"""
MindBus-only test for Docker debugging.
This tests if the issue is in MindBus/pika connections.
"""

import logging
import time
import threading

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mindbus.core import MindBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def on_event(event: dict, data: dict) -> None:
    """Handle incoming events."""
    logger.info(f"Received event: type={event.get('type')}")


def main():
    print("\n" + "="*60)
    print("MINDBUS-ONLY TEST - No FastAPI")
    print("="*60)

    # Test 1: Basic connection
    print("\n[TEST 1] Connecting to RabbitMQ...")
    bus = MindBus()
    bus.connect()
    print("✓ Connected successfully")

    # Test 2: Subscribe
    print("\n[TEST 2] Subscribing to events...")
    bus.subscribe("evt.#", on_event)
    print("✓ Subscribed to evt.# pattern")

    # Test 3: Start consuming in background
    print("\n[TEST 3] Starting consume loop in background thread...")

    def consume_loop():
        try:
            bus.start_consuming()
        except Exception as e:
            logger.error(f"Consume error: {e}")

    thread = threading.Thread(target=consume_loop, daemon=True)
    thread.start()
    print("✓ Consume thread started")

    # Test 4: Wait and check Docker
    print("\n[TEST 4] Waiting 3 minutes to see if Docker crashes...")
    print("Check Docker status manually with: docker ps")
    print("Press Ctrl+C to stop early\n")

    try:
        for i in range(180):  # 3 minutes
            time.sleep(1)
            if i % 30 == 0:
                print(f"  ... {i} seconds elapsed, Docker still running?")
    except KeyboardInterrupt:
        print("\n\nStopped by user")

    print("\n[CLEANUP] Disconnecting...")
    bus.stop_consuming()
    bus.disconnect()
    print("✓ Done")


if __name__ == "__main__":
    main()
