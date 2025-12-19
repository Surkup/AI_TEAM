#!/usr/bin/env python3
"""
End-to-End Integration Tests for AI_TEAM.

Tests the full integration:
- Orchestrator → Agent → Storage

This validates that all components work together correctly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestrator.integrated_orchestrator import IntegratedOrchestrator
from orchestrator.models import ProcessStatus, StepStatus
from agents.dummy_agent import DummyAgent
from services.storage_service import StorageService


# =============================================================================
# Test Results Tracking
# =============================================================================

class TestResults:
    def __init__(self):
        self.tests = []
        self.current_category = None

    def set_category(self, name: str):
        self.current_category = name
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

    def add(self, name: str, passed: bool, error: str = None):
        self.tests.append({
            "category": self.current_category,
            "name": name,
            "passed": passed,
            "error": error
        })
        icon = "✅" if passed else "❌"
        if error and not passed:
            print(f"  {icon} {name}: {error[:60]}")
        else:
            print(f"  {icon} {name}")

    def summary(self):
        print(f"\n{'='*60}")
        print("  SUMMARY")
        print(f"{'='*60}")

        passed = sum(1 for t in self.tests if t["passed"])
        total = len(self.tests)

        categories = {}
        for t in self.tests:
            cat = t["category"]
            if cat not in categories:
                categories[cat] = {"passed": 0, "total": 0}
            categories[cat]["total"] += 1
            if t["passed"]:
                categories[cat]["passed"] += 1

        for cat, stats in categories.items():
            status = "✅" if stats["passed"] == stats["total"] else "⚠️"
            print(f"  {status} {cat}: {stats['passed']}/{stats['total']}")

        print(f"\n  Total: {passed}/{total} tests passed")

        if passed == total:
            print("\n  🎉 ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n  ⚠️  {total - passed} tests failed")
            return 1


results = TestResults()


# =============================================================================
# Helper: Create Test Orchestrator
# =============================================================================

def create_orchestrator() -> IntegratedOrchestrator:
    """Create orchestrator with all components."""
    orch = IntegratedOrchestrator()
    orch.init_storage()

    # Register dummy agent
    dummy = DummyAgent()
    orch.register_local_agent("generate_text", dummy)
    orch.register_local_agent("research", dummy)
    orch.register_local_agent("test.echo", dummy)

    return orch


# =============================================================================
# 1. Basic Integration Tests
# =============================================================================

def test_basic_integration():
    results.set_category("1. BASIC INTEGRATION")

    orch = create_orchestrator()

    # Test 1.1: Simple process execution
    try:
        card_data = {
            "metadata": {"name": "test_simple"},
            "spec": {
                "steps": [
                    {"id": "step1", "action": "test.echo", "params": {"message": "hello"}},
                    {"id": "done", "type": "complete", "status": "success"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card)
        results.add("Simple process completes", instance.status == ProcessStatus.COMPLETED)
    except Exception as e:
        results.add("Simple process completes", False, str(e))

    # Test 1.2: Process with input params
    try:
        card_data = {
            "metadata": {"name": "test_input"},
            "spec": {
                "variables": {"result": None},
                "steps": [
                    {"id": "gen", "action": "generate_text", "params": {"prompt": "${input.topic}"}, "output": "result"},
                    {"id": "done", "type": "complete", "result": "${result}"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card, {"topic": "AI trends"})
        results.add("Input params passed to agent",
                   instance.status == ProcessStatus.COMPLETED and instance.result is not None)
    except Exception as e:
        results.add("Input params passed to agent", False, str(e))

    # Test 1.3: Multi-step process
    try:
        card_data = {
            "metadata": {"name": "test_multistep"},
            "spec": {
                "variables": {"step1_out": None, "step2_out": None},
                "steps": [
                    {"id": "s1", "action": "test.echo", "params": {"msg": "first"}, "output": "step1_out"},
                    {"id": "s2", "action": "test.echo", "params": {"msg": "second"}, "output": "step2_out"},
                    {"id": "s3", "action": "test.echo", "params": {"msg": "third"}},
                    {"id": "done", "type": "complete"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card)
        results.add("Multi-step process completes",
                   instance.status == ProcessStatus.COMPLETED and len(instance.step_results) >= 3)
    except Exception as e:
        results.add("Multi-step process completes", False, str(e))


# =============================================================================
# 2. Storage Integration Tests
# =============================================================================

def test_storage_integration():
    results.set_category("2. STORAGE INTEGRATION")

    orch = create_orchestrator()

    # Test 2.1: Process saves to storage
    try:
        card_data = {
            "metadata": {"name": "test_storage"},
            "spec": {
                "steps": [
                    {"id": "save", "action": "file_storage", "params": {"path": "/test/e2e.txt", "content": "E2E test content"}},
                    {"id": "done", "type": "complete"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card)
        results.add("Process saves to storage", instance.status == ProcessStatus.COMPLETED)
    except Exception as e:
        results.add("Process saves to storage", False, str(e))

    # Test 2.2: Verify file in storage
    try:
        file_result = orch.storage.handle_command("read_file", {"path": "/test/e2e.txt"})
        results.add("File readable from storage", file_result["content"] == "E2E test content")
    except Exception as e:
        results.add("File readable from storage", False, str(e))

    # Test 2.3: Process result saved as artifact
    try:
        card_data = {
            "metadata": {"name": "test_artifact"},
            "spec": {
                "steps": [
                    {"id": "gen", "action": "test.echo", "params": {"msg": "artifact test"}},
                    {"id": "done", "type": "complete"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card)

        # Check artifact was saved
        artifact = orch.storage.handle_command("get_artifact", {
            "artifact_id": f"process-{instance.id}"
        })
        results.add("Process result saved as artifact",
                   artifact["data"]["status"] == "completed")
    except Exception as e:
        results.add("Process result saved as artifact", False, str(e))


# =============================================================================
# 3. Variable Resolution Tests
# =============================================================================

def test_variable_resolution():
    results.set_category("3. VARIABLE RESOLUTION")

    orch = create_orchestrator()

    # Test 3.1: Simple variable passing
    try:
        card_data = {
            "metadata": {"name": "test_vars"},
            "spec": {
                "variables": {"generated": None},
                "steps": [
                    {"id": "gen", "action": "test.echo", "params": {"msg": "hello"}, "output": "generated"},
                    {"id": "save", "action": "file_storage", "params": {
                        "path": "/test/var_test.txt",
                        "content": "Result: ${generated}"
                    }},
                    {"id": "done", "type": "complete", "result": "${generated}"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card)
        results.add("Variables passed between steps",
                   instance.status == ProcessStatus.COMPLETED and instance.result is not None)
    except Exception as e:
        results.add("Variables passed between steps", False, str(e))

    # Test 3.2: Nested input variables
    try:
        card_data = {
            "metadata": {"name": "test_nested"},
            "spec": {
                "steps": [
                    {"id": "use", "action": "test.echo", "params": {"msg": "${input.data.value}"}},
                    {"id": "done", "type": "complete"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card, {"data": {"value": "nested_value"}})
        results.add("Nested input variables resolved", instance.status == ProcessStatus.COMPLETED)
    except Exception as e:
        results.add("Nested input variables resolved", False, str(e))


# =============================================================================
# 4. Process Card Loading Tests
# =============================================================================

def test_card_loading():
    results.set_category("4. PROCESS CARD LOADING")

    orch = create_orchestrator()

    # Test 4.1: Load simple_text_generation.yaml
    try:
        card = orch.load_card("config/process_cards/simple_text_generation.yaml")
        results.add("Load simple_text_generation.yaml", card.metadata.name == "simple_text_generation")
    except Exception as e:
        results.add("Load simple_text_generation.yaml", False, str(e))

    # Test 4.2: Execute loaded card
    try:
        card = orch.load_card("config/process_cards/simple_text_generation.yaml")
        instance = orch.execute_process(card, {"prompt": "test prompt"})
        results.add("Execute loaded card", instance.status == ProcessStatus.COMPLETED)
    except Exception as e:
        results.add("Execute loaded card", False, str(e))


# =============================================================================
# 5. Error Handling Tests
# =============================================================================

def test_error_handling():
    results.set_category("5. ERROR HANDLING")

    orch = create_orchestrator()

    # Test 5.1: Unknown capability fails gracefully
    try:
        card_data = {
            "metadata": {"name": "test_unknown"},
            "spec": {
                "steps": [
                    {"id": "fail", "action": "nonexistent_capability", "params": {}},
                    {"id": "done", "type": "complete"}
                ]
            }
        }
        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card)
        results.add("Unknown capability fails process", instance.status == ProcessStatus.FAILED)
    except Exception as e:
        # Exception is acceptable for unknown capability
        results.add("Unknown capability fails process", True)

    # Test 5.2: Invalid card rejected
    try:
        card_data = {
            "metadata": {"name": "test_invalid"},
            "spec": {
                "steps": []  # No steps
            }
        }
        orch.load_card_from_dict(card_data)
        results.add("Invalid card rejected", False, "Should have raised")
    except ValueError:
        results.add("Invalid card rejected", True)
    except Exception as e:
        results.add("Invalid card rejected", False, str(type(e)))


# =============================================================================
# 6. Full Workflow Tests
# =============================================================================

def test_full_workflow():
    results.set_category("6. FULL WORKFLOW")

    orch = create_orchestrator()

    # Test 6.1: Complete workflow with all components
    # Note: DummyAgent returns dict output. In real usage, you'd extract text.
    # This test uses a simplified workflow that works with mock data.
    try:
        card_data = {
            "metadata": {
                "name": "full_workflow_test",
                "version": "1.0",
                "description": "Test complete workflow"
            },
            "spec": {
                "variables": {
                    "step1_out": None,
                    "step2_out": None
                },
                "steps": [
                    {
                        "id": "step1",
                        "action": "test.echo",
                        "params": {"topic": "${input.topic}"},
                        "output": "step1_out"
                    },
                    {
                        "id": "step2",
                        "action": "test.echo",
                        "params": {"data": "processed"},
                        "output": "step2_out"
                    },
                    {
                        "id": "save",
                        "action": "file_storage",
                        "params": {
                            "path": "/workflow/${input.topic}.txt",
                            "content": "Workflow result for topic: ${input.topic}"
                        }
                    },
                    {
                        "id": "complete",
                        "type": "complete",
                        "status": "success",
                        "result": "${step2_out}"
                    }
                ]
            }
        }

        card = orch.load_card_from_dict(card_data)
        instance = orch.execute_process(card, {"topic": "e2e_test"})

        results.add("Full workflow completes", instance.status == ProcessStatus.COMPLETED)
        results.add("Full workflow has result", instance.result is not None)

        # Verify file was saved
        try:
            file_result = orch.storage.handle_command("read_file", {"path": "/workflow/e2e_test.txt"})
            results.add("Full workflow saves file", "Workflow result" in file_result["content"])
        except Exception:
            results.add("Full workflow saves file", False, "File not found")

        # Verify all steps completed
        completed_steps = [r for r in instance.step_results if r.status == StepStatus.COMPLETED]
        results.add("All steps completed", len(completed_steps) == 4)

    except Exception as e:
        results.add("Full workflow completes", False, str(e))
        results.add("Full workflow has result", False, "skipped")
        results.add("Full workflow saves file", False, "skipped")
        results.add("All steps completed", False, "skipped")


# =============================================================================
# 7. Stats and Monitoring Tests
# =============================================================================

def test_stats():
    results.set_category("7. STATS AND MONITORING")

    orch = create_orchestrator()

    # Run a few processes
    card_data = {
        "metadata": {"name": "stats_test"},
        "spec": {"steps": [{"id": "done", "type": "complete"}]}
    }
    card = orch.load_card_from_dict(card_data)
    orch.execute_process(card)
    orch.execute_process(card)

    # Test 7.1: Get orchestrator stats
    try:
        stats = orch.get_stats()
        results.add("Get orchestrator stats",
                   stats["processes"]["total"] >= 2 and stats["processes"]["completed"] >= 2)
    except Exception as e:
        results.add("Get orchestrator stats", False, str(e))

    # Test 7.2: Get storage stats
    try:
        storage_stats = orch.storage.handle_command("get_stats", {})
        results.add("Get storage stats", "files_count" in storage_stats["stats"])
    except Exception as e:
        results.add("Get storage stats", False, str(e))


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "🔗" * 30)
    print("  END-TO-END INTEGRATION TESTS")
    print("🔗" * 30)

    test_basic_integration()
    test_storage_integration()
    test_variable_resolution()
    test_card_loading()
    test_error_handling()
    test_full_workflow()
    test_stats()

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
