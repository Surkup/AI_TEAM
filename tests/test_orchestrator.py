#!/usr/bin/env python3
"""
Tests for Orchestrator.

Tests cover:
1. ProcessCard model validation
2. ProcessCard loading from YAML
3. Variable resolution
4. Step execution
5. Process lifecycle
6. Condition evaluation
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestrator.models import (
    ProcessCard,
    ProcessMetadata,
    ProcessSpec,
    StepSpec,
    StepType,
    ProcessStatus,
    StepStatus,
    ProcessInstance,
    StepResult,
    RetryPolicy,
)
from orchestrator.simple_orchestrator import SimpleOrchestrator
from registry.models import NodeType


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
# Test Data
# =============================================================================

SIMPLE_CARD_DATA = {
    "metadata": {
        "id": "test-card-001",
        "name": "test_process",
        "version": "1.0",
        "description": "Test process card"
    },
    "spec": {
        "variables": {
            "topic": "",
            "result": None
        },
        "steps": [
            {
                "id": "step_1",
                "action": "generate_text",
                "params": {"prompt": "${input.topic}"},
                "output": "result"
            },
            {
                "id": "step_complete",
                "type": "complete",
                "status": "success",
                "result": "${result}"
            }
        ]
    }
}

CONDITIONAL_CARD_DATA = {
    "metadata": {
        "id": "test-card-002",
        "name": "conditional_process",
        "version": "1.0"
    },
    "spec": {
        "variables": {
            "score": 0
        },
        "steps": [
            {
                "id": "check_score",
                "condition": "${score} >= 5",
                "then": "success_step",
                "else": "failure_step"
            },
            {
                "id": "success_step",
                "type": "complete",
                "status": "success"
            },
            {
                "id": "failure_step",
                "type": "complete",
                "status": "failure"
            }
        ]
    }
}


# =============================================================================
# 1. ProcessCard Model Tests
# =============================================================================

def test_process_card_models():
    results.set_category("1. PROCESS CARD MODELS")

    # Test 1.1: Create ProcessMetadata
    try:
        metadata = ProcessMetadata(name="test", version="1.0")
        results.add("Create ProcessMetadata", metadata.name == "test")
    except Exception as e:
        results.add("Create ProcessMetadata", False, str(e))

    # Test 1.2: ProcessMetadata generates UUID
    try:
        metadata = ProcessMetadata(name="test")
        results.add("ProcessMetadata generates UUID", len(metadata.id) > 0)
    except Exception as e:
        results.add("ProcessMetadata generates UUID", False, str(e))

    # Test 1.3: Create StepSpec
    try:
        step = StepSpec(id="step_1", action="test_action")
        results.add("Create StepSpec", step.id == "step_1")
    except Exception as e:
        results.add("Create StepSpec", False, str(e))

    # Test 1.4: StepSpec type inference - execute
    try:
        step = StepSpec(id="step_1", action="test")
        results.add("StepSpec infers EXECUTE type", step.get_type() == StepType.EXECUTE)
    except Exception as e:
        results.add("StepSpec infers EXECUTE type", False, str(e))

    # Test 1.5: StepSpec type inference - condition
    try:
        step = StepSpec(id="step_1", condition="true", then="next")
        results.add("StepSpec infers CONDITION type", step.get_type() == StepType.CONDITION)
    except Exception as e:
        results.add("StepSpec infers CONDITION type", False, str(e))

    # Test 1.6: StepSpec type inference - complete
    try:
        step = StepSpec(id="step_1", type=StepType.COMPLETE)
        results.add("StepSpec explicit COMPLETE type", step.get_type() == StepType.COMPLETE)
    except Exception as e:
        results.add("StepSpec explicit COMPLETE type", False, str(e))

    # Test 1.7: Create ProcessCard from dict
    try:
        card = ProcessCard.model_validate(SIMPLE_CARD_DATA)
        results.add("Create ProcessCard from dict", card.metadata.name == "test_process")
    except Exception as e:
        results.add("Create ProcessCard from dict", False, str(e))

    # Test 1.8: ProcessCard get_step
    try:
        card = ProcessCard.model_validate(SIMPLE_CARD_DATA)
        step = card.get_step("step_1")
        results.add("ProcessCard get_step", step is not None and step.action == "generate_text")
    except Exception as e:
        results.add("ProcessCard get_step", False, str(e))

    # Test 1.9: ProcessCard get_first_step
    try:
        card = ProcessCard.model_validate(SIMPLE_CARD_DATA)
        step = card.get_first_step()
        results.add("ProcessCard get_first_step", step is not None and step.id == "step_1")
    except Exception as e:
        results.add("ProcessCard get_first_step", False, str(e))

    # Test 1.10: ProcessCard validate_references - valid
    try:
        card = ProcessCard.model_validate(CONDITIONAL_CARD_DATA)
        errors = card.validate_references()
        results.add("ProcessCard validate_references (valid)", len(errors) == 0)
    except Exception as e:
        results.add("ProcessCard validate_references (valid)", False, str(e))

    # Test 1.11: ProcessCard validate_references - invalid
    try:
        invalid_data = {
            "metadata": {"name": "test"},
            "spec": {
                "steps": [
                    {"id": "step_1", "condition": "true", "then": "nonexistent"}
                ]
            }
        }
        card = ProcessCard.model_validate(invalid_data)
        errors = card.validate_references()
        results.add("ProcessCard validate_references (invalid)", len(errors) > 0)
    except Exception as e:
        results.add("ProcessCard validate_references (invalid)", False, str(e))


# =============================================================================
# 2. RetryPolicy Tests
# =============================================================================

def test_retry_policy():
    results.set_category("2. RETRY POLICY")

    # Test 2.1: Create valid RetryPolicy
    try:
        policy = RetryPolicy(max_attempts=3, delay_seconds=5)
        results.add("Create RetryPolicy", policy.max_attempts == 3)
    except Exception as e:
        results.add("Create RetryPolicy", False, str(e))

    # Test 2.2: RetryPolicy defaults
    try:
        policy = RetryPolicy()
        results.add("RetryPolicy defaults", policy.on_failure == "abort")
    except Exception as e:
        results.add("RetryPolicy defaults", False, str(e))

    # Test 2.3: RetryPolicy max_attempts limit
    try:
        RetryPolicy(max_attempts=15)  # > 10
        results.add("RetryPolicy max_attempts limit", False, "Should reject > 10")
    except ValueError:
        results.add("RetryPolicy max_attempts limit", True)
    except Exception as e:
        results.add("RetryPolicy max_attempts limit", False, str(e))

    # Test 2.4: RetryPolicy invalid on_failure
    try:
        RetryPolicy(on_failure="invalid")
        results.add("RetryPolicy invalid on_failure", False, "Should reject")
    except ValueError:
        results.add("RetryPolicy invalid on_failure rejected", True)
    except Exception as e:
        results.add("RetryPolicy invalid on_failure rejected", False, str(e))


# =============================================================================
# 3. ProcessInstance Tests
# =============================================================================

def test_process_instance():
    results.set_category("3. PROCESS INSTANCE")

    # Test 3.1: Create ProcessInstance
    try:
        instance = ProcessInstance(card_id="card-1", card_name="test")
        results.add("Create ProcessInstance", instance.status == ProcessStatus.PENDING)
    except Exception as e:
        results.add("Create ProcessInstance", False, str(e))

    # Test 3.2: ProcessInstance generates UUID
    try:
        instance = ProcessInstance(card_id="card-1", card_name="test")
        results.add("ProcessInstance generates UUID", len(instance.id) > 0)
    except Exception as e:
        results.add("ProcessInstance generates UUID", False, str(e))

    # Test 3.3: Add step result
    try:
        instance = ProcessInstance(card_id="card-1", card_name="test")
        result = StepResult(step_id="step_1", status=StepStatus.COMPLETED)
        instance.add_step_result(result)
        results.add("Add step result", len(instance.step_results) == 1)
    except Exception as e:
        results.add("Add step result", False, str(e))

    # Test 3.4: Get step result
    try:
        instance = ProcessInstance(card_id="card-1", card_name="test")
        result = StepResult(step_id="step_1", status=StepStatus.COMPLETED)
        instance.add_step_result(result)
        retrieved = instance.get_step_result("step_1")
        results.add("Get step result", retrieved is not None and retrieved.status == StepStatus.COMPLETED)
    except Exception as e:
        results.add("Get step result", False, str(e))


# =============================================================================
# 4. Orchestrator Variable Resolution Tests
# =============================================================================

def test_variable_resolution():
    results.set_category("4. VARIABLE RESOLUTION")

    orchestrator = SimpleOrchestrator()

    # Test 4.1: Simple variable
    try:
        variables = {"topic": "AI"}
        result = orchestrator._resolve_variable("${topic}", variables)
        results.add("Resolve simple variable", result == "AI")
    except Exception as e:
        results.add("Resolve simple variable", False, str(e))

    # Test 4.2: Nested variable
    try:
        variables = {"input": {"topic": "Machine Learning"}}
        result = orchestrator._resolve_variable("${input.topic}", variables)
        results.add("Resolve nested variable", result == "Machine Learning")
    except Exception as e:
        results.add("Resolve nested variable", False, str(e))

    # Test 4.3: Variable in string
    try:
        variables = {"name": "World"}
        result = orchestrator._resolve_variable("Hello, ${name}!", variables)
        results.add("Variable in string", result == "Hello, World!")
    except Exception as e:
        results.add("Variable in string", False, str(e))

    # Test 4.4: Missing variable unchanged
    try:
        variables = {}
        result = orchestrator._resolve_variable("${missing}", variables)
        results.add("Missing variable unchanged", result == "${missing}")
    except Exception as e:
        results.add("Missing variable unchanged", False, str(e))

    # Test 4.5: Resolve params dict
    try:
        variables = {"topic": "Python", "count": 5}
        params = {"subject": "${topic}", "limit": "${count}"}
        result = orchestrator._resolve_params(params, variables)
        results.add("Resolve params dict", result["subject"] == "Python")
    except Exception as e:
        results.add("Resolve params dict", False, str(e))


# =============================================================================
# 5. Orchestrator Condition Evaluation Tests
# =============================================================================

def test_condition_evaluation():
    results.set_category("5. CONDITION EVALUATION")

    orchestrator = SimpleOrchestrator()

    # Test 5.1: True condition
    try:
        variables = {}
        result = orchestrator._evaluate_condition("true", variables)
        results.add("Evaluate 'true'", result == True)
    except Exception as e:
        results.add("Evaluate 'true'", False, str(e))

    # Test 5.2: False condition
    try:
        result = orchestrator._evaluate_condition("false", {})
        results.add("Evaluate 'false'", result == False)
    except Exception as e:
        results.add("Evaluate 'false'", False, str(e))

    # Test 5.3: Comparison condition
    try:
        variables = {"score": 8}
        result = orchestrator._evaluate_condition("score >= 5", variables)
        results.add("Evaluate comparison (true)", result == True)
    except Exception as e:
        results.add("Evaluate comparison (true)", False, str(e))

    # Test 5.4: Comparison condition (false)
    try:
        variables = {"score": 3}
        result = orchestrator._evaluate_condition("score >= 5", variables)
        results.add("Evaluate comparison (false)", result == False)
    except Exception as e:
        results.add("Evaluate comparison (false)", False, str(e))

    # Test 5.5: Variable in condition
    try:
        variables = {"count": 10}
        result = orchestrator._evaluate_condition("${count} > 5", variables)
        results.add("Variable in condition", result == True)
    except Exception as e:
        results.add("Variable in condition", False, str(e))


# =============================================================================
# 6. Orchestrator Process Loading Tests
# =============================================================================

def test_process_loading():
    results.set_category("6. PROCESS LOADING")

    orchestrator = SimpleOrchestrator()

    # Test 6.1: Load card from dict
    try:
        card = orchestrator.load_card_from_dict(SIMPLE_CARD_DATA)
        results.add("Load card from dict", card.metadata.name == "test_process")
    except Exception as e:
        results.add("Load card from dict", False, str(e))

    # Test 6.2: Load card from YAML file
    try:
        card = orchestrator.load_card("config/process_cards/simple_text_generation.yaml")
        results.add("Load card from YAML", card.metadata.name == "simple_text_generation")
    except Exception as e:
        results.add("Load card from YAML", False, str(e))

    # Test 6.3: Load invalid card
    try:
        invalid_data = {"metadata": {"name": "test"}, "spec": {"steps": []}}
        orchestrator.load_card_from_dict(invalid_data)
        results.add("Reject invalid card (no steps)", False, "Should reject")
    except ValueError:
        results.add("Reject invalid card (no steps)", True)
    except Exception as e:
        results.add("Reject invalid card (no steps)", False, str(type(e)))


# =============================================================================
# 7. Orchestrator Process Execution Tests
# =============================================================================

def test_process_execution():
    results.set_category("7. PROCESS EXECUTION")

    orchestrator = SimpleOrchestrator()

    # Test 7.1: Start process
    try:
        card = orchestrator.load_card_from_dict(SIMPLE_CARD_DATA)
        instance = orchestrator.start_process(card, {"topic": "AI"})
        results.add("Start process", instance.status == ProcessStatus.RUNNING)
    except Exception as e:
        results.add("Start process", False, str(e))

    # Test 7.2: Process has input variables
    try:
        card = orchestrator.load_card_from_dict(SIMPLE_CARD_DATA)
        instance = orchestrator.start_process(card, {"topic": "Test"})
        results.add("Process has input variables", instance.variables.get("input", {}).get("topic") == "Test")
    except Exception as e:
        results.add("Process has input variables", False, str(e))

    # Test 7.3: Get process
    try:
        card = orchestrator.load_card_from_dict(SIMPLE_CARD_DATA)
        instance = orchestrator.start_process(card)
        retrieved = orchestrator.get_process(instance.id)
        results.add("Get process by ID", retrieved is not None)
    except Exception as e:
        results.add("Get process by ID", False, str(e))

    # Test 7.4: Get all processes
    try:
        processes = orchestrator.get_all_processes()
        results.add("Get all processes", len(processes) >= 1)
    except Exception as e:
        results.add("Get all processes", False, str(e))


# =============================================================================
# 8. Orchestrator Registration Tests
# =============================================================================

def test_orchestrator_registration():
    results.set_category("8. ORCHESTRATOR REGISTRATION")

    orchestrator = SimpleOrchestrator()

    # Test 8.1: Build passport
    try:
        passport = orchestrator._build_passport()
        results.add("Build passport", passport is not None)
    except Exception as e:
        results.add("Build passport", False, str(e))

    # Test 8.2: Passport node_type is ORCHESTRATOR
    try:
        passport = orchestrator._build_passport()
        results.add("Passport node_type is ORCHESTRATOR",
                   passport.metadata.node_type == NodeType.ORCHESTRATOR)
    except Exception as e:
        results.add("Passport node_type is ORCHESTRATOR", False, str(e))

    # Test 8.3: Passport has capabilities
    try:
        passport = orchestrator._build_passport()
        cap_names = [cap.name for cap in passport.spec.capabilities]
        results.add("Passport has capabilities",
                   "process_execution" in cap_names and "task_routing" in cap_names)
    except Exception as e:
        results.add("Passport has capabilities", False, str(e))

    # Test 8.4: Get stats
    try:
        stats = orchestrator.get_stats()
        results.add("Get stats", "processes" in stats)
    except Exception as e:
        results.add("Get stats", False, str(e))


# =============================================================================
# 9. Duration Parsing Tests
# =============================================================================

def test_duration_parsing():
    results.set_category("9. DURATION PARSING")

    orchestrator = SimpleOrchestrator()

    # Test 9.1: Parse seconds
    try:
        result = orchestrator._parse_duration("5s")
        results.add("Parse '5s'", result == 5.0)
    except Exception as e:
        results.add("Parse '5s'", False, str(e))

    # Test 9.2: Parse minutes
    try:
        result = orchestrator._parse_duration("2m")
        results.add("Parse '2m'", result == 120.0)
    except Exception as e:
        results.add("Parse '2m'", False, str(e))

    # Test 9.3: Parse hours
    try:
        result = orchestrator._parse_duration("1h")
        results.add("Parse '1h'", result == 3600.0)
    except Exception as e:
        results.add("Parse '1h'", False, str(e))

    # Test 9.4: Parse plain number
    try:
        result = orchestrator._parse_duration("30")
        results.add("Parse '30'", result == 30.0)
    except Exception as e:
        results.add("Parse '30'", False, str(e))


# =============================================================================
# 10. Step ID Validation Tests
# =============================================================================

def test_step_id_validation():
    results.set_category("10. STEP ID VALIDATION")

    # Test 10.1: Unique step IDs pass
    try:
        data = {
            "metadata": {"name": "test"},
            "spec": {
                "steps": [
                    {"id": "step_1", "action": "test"},
                    {"id": "step_2", "action": "test"}
                ]
            }
        }
        card = ProcessCard.model_validate(data)
        results.add("Unique step IDs pass", len(card.spec.steps) == 2)
    except Exception as e:
        results.add("Unique step IDs pass", False, str(e))

    # Test 10.2: Duplicate step IDs rejected
    try:
        data = {
            "metadata": {"name": "test"},
            "spec": {
                "steps": [
                    {"id": "step_1", "action": "test"},
                    {"id": "step_1", "action": "test2"}
                ]
            }
        }
        ProcessCard.model_validate(data)
        results.add("Duplicate step IDs rejected", False, "Should reject")
    except ValueError:
        results.add("Duplicate step IDs rejected", True)
    except Exception as e:
        results.add("Duplicate step IDs rejected", False, str(type(e)))


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "🎯" * 30)
    print("  ORCHESTRATOR TEST SUITE")
    print("🎯" * 30)

    test_process_card_models()
    test_retry_policy()
    test_process_instance()
    test_variable_resolution()
    test_condition_evaluation()
    test_process_loading()
    test_process_execution()
    test_orchestrator_registration()
    test_duration_parsing()
    test_step_id_validation()

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
