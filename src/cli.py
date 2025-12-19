#!/usr/bin/env python3
"""
AI_TEAM CLI — Command Line Interface for running tasks.

Usage:
    ./venv/bin/python -m src.cli run <process_card> [--input key=value ...]
    ./venv/bin/python -m src.cli list-cards
    ./venv/bin/python -m src.cli status
    ./venv/bin/python -m src.cli demo

Examples:
    # Run a simple text generation
    ./venv/bin/python -m src.cli run simple_text_generation --input prompt="Hello world"

    # Run article generation
    ./venv/bin/python -m src.cli run article_generation --input topic="AI trends"

    # List available process cards
    ./venv/bin/python -m src.cli list-cards

    # Run interactive demo
    ./venv/bin/python -m src.cli demo
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.integrated_orchestrator import IntegratedOrchestrator
from src.orchestrator.models import ProcessStatus, StepStatus
from src.agents.dummy_agent import DummyAgent


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s' if verbose else '%(message)s'
    )
    # Quiet down noisy loggers
    if not verbose:
        logging.getLogger("pika").setLevel(logging.WARNING)
        logging.getLogger("src.mindbus").setLevel(logging.WARNING)
        logging.getLogger("src.orchestrator").setLevel(logging.WARNING)
        logging.getLogger("src.registry").setLevel(logging.WARNING)


def parse_input_params(input_args: list) -> Dict[str, Any]:
    """Parse --input key=value arguments into a dictionary."""
    params = {}
    for arg in input_args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            # Try to parse as number or bool
            if value.lower() == "true":
                params[key] = True
            elif value.lower() == "false":
                params[key] = False
            else:
                try:
                    params[key] = int(value)
                except ValueError:
                    try:
                        params[key] = float(value)
                    except ValueError:
                        params[key] = value
        else:
            print(f"Warning: Invalid input format '{arg}', expected key=value")
    return params


def find_process_card(name: str) -> Optional[Path]:
    """Find process card by name or path."""
    # Check if it's a direct path
    if Path(name).exists():
        return Path(name)

    # Check in process_cards directory
    cards_dir = Path("config/process_cards")
    if not name.endswith(".yaml"):
        name = f"{name}.yaml"

    card_path = cards_dir / name
    if card_path.exists():
        return card_path

    return None


def list_process_cards():
    """List all available process cards."""
    cards_dir = Path("config/process_cards")

    print("\n📋 Available Process Cards:")
    print("=" * 50)

    if not cards_dir.exists():
        print("  (no process cards directory found)")
        return

    cards = list(cards_dir.glob("*.yaml"))
    if not cards:
        print("  (no process cards found)")
        return

    for card_path in sorted(cards):
        name = card_path.stem
        print(f"  - {name}")

    print()
    print("Usage: ./venv/bin/python -m src.cli run <card_name> --input key=value")


def show_status(orchestrator: IntegratedOrchestrator):
    """Show system status."""
    stats = orchestrator.get_stats()

    print("\n📊 AI_TEAM Status:")
    print("=" * 50)
    print(f"  Orchestrator: {stats['name']}")
    print(f"  Local agents: {', '.join(stats['local_agents']) or '(none)'}")
    print(f"  Processes: {stats['processes']['total']} total")
    print(f"    - Completed: {stats['processes']['completed']}")
    print(f"    - Failed: {stats['processes']['failed']}")

    if orchestrator.storage:
        storage_stats = orchestrator.storage.handle_command("get_stats", {})
        print(f"\n  Storage: {storage_stats['stats']['storage_type']}")
        print(f"    - Files: {storage_stats['stats']['files_count']}")
        print(f"    - Artifacts: {storage_stats['stats']['artifacts_count']}")


def run_process(args):
    """Run a process card."""
    # Find the card
    card_path = find_process_card(args.card)
    if card_path is None:
        print(f"\n❌ Process card not found: {args.card}")
        print("   Use 'list-cards' to see available cards")
        return 1

    # Parse input params
    input_params = parse_input_params(args.input or [])

    print(f"\n🚀 Running process: {card_path.stem}")
    print(f"   Input: {input_params or '(none)'}")
    print("=" * 50)

    # Initialize orchestrator
    orchestrator = IntegratedOrchestrator()
    orchestrator.init_storage()

    # Register a dummy agent for testing
    dummy = DummyAgent()
    orchestrator.register_local_agent("generate_text", dummy)
    orchestrator.register_local_agent("research", dummy)
    orchestrator.register_local_agent("review_text", dummy)
    orchestrator.register_local_agent("improve_text", dummy)
    orchestrator.register_local_agent("test.echo", dummy)

    # Load and execute
    try:
        card = orchestrator.load_card(str(card_path))
        print(f"\n📄 Card: {card.metadata.name} v{card.metadata.version}")
        print(f"   Description: {card.metadata.description or '(none)'}")
        print(f"   Steps: {len(card.spec.steps)}")

        print("\n⏳ Executing steps...")

        instance = orchestrator.execute_process(card, input_params)

        # Show results
        print("\n" + "=" * 50)

        if instance.status == ProcessStatus.COMPLETED:
            print(f"✅ Process completed successfully!")
            print(f"   Duration: {instance.duration_seconds():.2f}s")
            print(f"   Steps executed: {len(instance.step_results)}")

            if instance.result:
                print(f"\n📤 Result:")
                if isinstance(instance.result, dict):
                    for key, value in instance.result.items():
                        value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                        print(f"     {key}: {value_str}")
                else:
                    print(f"     {instance.result}")

        elif instance.status == ProcessStatus.FAILED:
            print(f"❌ Process failed!")
            print(f"   Error: {instance.error}")
            return 1

        # Show step details if verbose
        if args.verbose:
            print("\n📋 Step Results:")
            for result in instance.step_results:
                icon = "✅" if result.status == StepStatus.COMPLETED else "❌"
                print(f"   {icon} {result.step_id}: {result.status.value}")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def run_demo():
    """Run interactive demo."""
    print("\n" + "=" * 60)
    print("   🎯 AI_TEAM Demo")
    print("=" * 60)
    print("\nThis demo shows the full integration:")
    print("  Orchestrator → Agent → Storage")
    print()

    # Initialize
    print("1️⃣  Initializing components...")
    orchestrator = IntegratedOrchestrator()
    orchestrator.init_storage()

    # Register dummy agent
    dummy = DummyAgent()
    orchestrator.register_local_agent("generate_text", dummy)
    orchestrator.register_local_agent("test.echo", dummy)
    print("   ✅ Orchestrator ready")
    print("   ✅ Storage ready")
    print("   ✅ DummyAgent registered")

    # Create a simple process card in-memory
    print("\n2️⃣  Creating process card...")
    card_data = {
        "metadata": {
            "name": "demo_process",
            "version": "1.0",
            "description": "Demo process for testing"
        },
        "spec": {
            "variables": {
                "text_result": None
            },
            "steps": [
                {
                    "id": "generate",
                    "action": "generate_text",
                    "params": {"prompt": "${input.prompt}"},
                    "output": "text_result"
                },
                {
                    "id": "save",
                    "action": "file_storage",
                    "params": {
                        "path": "/demo/output.txt",
                        # Note: DummyAgent returns dict, so we save a text summary
                        "content": "Generated text for prompt: ${input.prompt}"
                    }
                },
                {
                    "id": "complete",
                    "type": "complete",
                    "status": "success",
                    "result": "${text_result}"
                }
            ]
        }
    }
    card = orchestrator.load_card_from_dict(card_data)
    print(f"   ✅ Card loaded: {card.metadata.name}")
    print(f"   Steps: generate → save → complete")

    # Execute
    print("\n3️⃣  Executing process...")
    input_params = {"prompt": "Write a short greeting"}
    instance = orchestrator.execute_process(card, input_params)

    # Show result
    print("\n4️⃣  Results:")
    print(f"   Status: {instance.status.value}")
    print(f"   Duration: {instance.duration_seconds():.2f}s")

    if instance.result:
        print(f"   Output: {instance.result}")

    # Check storage
    print("\n5️⃣  Checking Storage...")
    try:
        file_result = orchestrator.storage.handle_command("read_file", {
            "path": "/demo/output.txt"
        })
        print(f"   ✅ File saved at: /demo/output.txt")
        print(f"   Content: {file_result['content'][:100]}...")
    except Exception as e:
        print(f"   ⚠️  File read failed: {e}")

    # Show stats
    print("\n6️⃣  Final Stats:")
    stats = orchestrator.get_stats()
    print(f"   Processes completed: {stats['processes']['completed']}")

    storage_stats = orchestrator.storage.handle_command("get_stats", {})
    print(f"   Files in storage: {storage_stats['stats']['files_count']}")
    print(f"   Artifacts in storage: {storage_stats['stats']['artifacts_count']}")

    print("\n" + "=" * 60)
    print("   ✅ Demo completed successfully!")
    print("=" * 60)

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI_TEAM CLI - Run AI agent processes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run simple_text_generation --input prompt="Hello"
  %(prog)s list-cards
  %(prog)s demo
  %(prog)s status
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a process card")
    run_parser.add_argument("card", help="Process card name or path")
    run_parser.add_argument("--input", "-i", action="append", help="Input parameters (key=value)")

    # list-cards command
    subparsers.add_parser("list-cards", help="List available process cards")

    # status command
    subparsers.add_parser("status", help="Show system status")

    # demo command
    subparsers.add_parser("demo", help="Run interactive demo")

    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.command == "run":
        return run_process(args)
    elif args.command == "list-cards":
        list_process_cards()
        return 0
    elif args.command == "status":
        orchestrator = IntegratedOrchestrator()
        orchestrator.init_storage()
        show_status(orchestrator)
        return 0
    elif args.command == "demo":
        return run_demo()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
