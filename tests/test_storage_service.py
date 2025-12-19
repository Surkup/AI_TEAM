#!/usr/bin/env python3
"""
Tests for Storage Service.

Tests cover:
1. File operations (save, read, list, delete)
2. Artifact operations
3. Storage limits
4. Error handling
5. Node registration as NodeType.STORAGE
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from registry.models import NodeType, NodePhase, ConditionStatus
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
# Create Test Service
# =============================================================================

def create_test_service() -> StorageService:
    """Create StorageService with test configuration."""
    return StorageService("config/services/storage.yaml")


# =============================================================================
# 1. Node Type Tests
# =============================================================================

def test_node_type():
    results.set_category("1. NODE TYPE TESTS")

    service = create_test_service()

    # Test 1.1: NodeType is STORAGE
    try:
        results.add("NodeType is STORAGE", service.node_type == NodeType.STORAGE)
    except Exception as e:
        results.add("NodeType is STORAGE", False, str(e))

    # Test 1.2: Service name from config
    try:
        results.add("Service name set", service.name == "storage-inmemory-01")
    except Exception as e:
        results.add("Service name set", False, str(e))

    # Test 1.3: Capabilities loaded
    try:
        has_file_storage = "file_storage" in service.capabilities
        has_artifact_storage = "artifact_storage" in service.capabilities
        results.add("Capabilities loaded", has_file_storage and has_artifact_storage)
    except Exception as e:
        results.add("Capabilities loaded", False, str(e))

    # Test 1.4: Build passport
    try:
        passport = service._build_passport()
        results.add("Build passport succeeds", passport is not None)
    except Exception as e:
        results.add("Build passport succeeds", False, str(e))

    # Test 1.5: Passport has correct node type
    try:
        passport = service._build_passport()
        results.add("Passport node_type is STORAGE",
                   passport.metadata.node_type == NodeType.STORAGE and
                   passport.spec.node_type == NodeType.STORAGE)
    except Exception as e:
        results.add("Passport node_type is STORAGE", False, str(e))

    # Test 1.6: Passport has capabilities
    try:
        passport = service._build_passport()
        cap_names = [cap.name for cap in passport.spec.capabilities]
        results.add("Passport has capabilities",
                   "file_storage" in cap_names and "artifact_storage" in cap_names)
    except Exception as e:
        results.add("Passport has capabilities", False, str(e))


# =============================================================================
# 2. File Operations Tests
# =============================================================================

def test_file_operations():
    results.set_category("2. FILE OPERATIONS TESTS")

    service = create_test_service()

    # Test 2.1: Save file
    try:
        result = service.handle_command("save_file", {
            "path": "/test/hello.txt",
            "content": "Hello, World!"
        })
        results.add("Save file", result["status"] == "completed")
    except Exception as e:
        results.add("Save file", False, str(e))

    # Test 2.2: Read file
    try:
        result = service.handle_command("read_file", {
            "path": "/test/hello.txt"
        })
        results.add("Read file", result["content"] == "Hello, World!")
    except Exception as e:
        results.add("Read file", False, str(e))

    # Test 2.3: File exists
    try:
        result = service.handle_command("file_exists", {
            "path": "/test/hello.txt"
        })
        results.add("File exists (true)", result["exists"] == True)
    except Exception as e:
        results.add("File exists (true)", False, str(e))

    # Test 2.4: File not exists
    try:
        result = service.handle_command("file_exists", {
            "path": "/nonexistent.txt"
        })
        results.add("File exists (false)", result["exists"] == False)
    except Exception as e:
        results.add("File exists (false)", False, str(e))

    # Test 2.5: Get file info
    try:
        result = service.handle_command("get_file_info", {
            "path": "/test/hello.txt"
        })
        results.add("Get file info", "metadata" in result and "size_bytes" in result["metadata"])
    except Exception as e:
        results.add("Get file info", False, str(e))

    # Test 2.6: List files
    try:
        service.handle_command("save_file", {"path": "/test/file1.txt", "content": "1"})
        service.handle_command("save_file", {"path": "/test/file2.txt", "content": "2"})
        result = service.handle_command("list_files", {"prefix": "/test/"})
        results.add("List files", result["count"] >= 2)
    except Exception as e:
        results.add("List files", False, str(e))

    # Test 2.7: Delete file
    try:
        result = service.handle_command("delete_file", {
            "path": "/test/hello.txt"
        })
        exists_result = service.handle_command("file_exists", {"path": "/test/hello.txt"})
        results.add("Delete file", result["status"] == "completed" and exists_result["exists"] == False)
    except Exception as e:
        results.add("Delete file", False, str(e))


# =============================================================================
# 3. Artifact Operations Tests
# =============================================================================

def test_artifact_operations():
    results.set_category("3. ARTIFACT OPERATIONS TESTS")

    service = create_test_service()

    # Test 3.1: Save artifact
    try:
        result = service.handle_command("save_artifact", {
            "artifact_id": "artifact-001",
            "task_id": "task-123",
            "process_id": "process-456",
            "data": {"result": "success", "output": "Hello"},
            "artifact_type": "result"
        })
        results.add("Save artifact", result["status"] == "completed")
    except Exception as e:
        results.add("Save artifact", False, str(e))

    # Test 3.2: Get artifact
    try:
        result = service.handle_command("get_artifact", {
            "artifact_id": "artifact-001"
        })
        results.add("Get artifact", result["data"]["result"] == "success")
    except Exception as e:
        results.add("Get artifact", False, str(e))

    # Test 3.3: Artifact metadata
    try:
        result = service.handle_command("get_artifact", {
            "artifact_id": "artifact-001"
        })
        meta = result["metadata"]
        results.add("Artifact metadata",
                   meta["task_id"] == "task-123" and
                   meta["artifact_type"] == "result")
    except Exception as e:
        results.add("Artifact metadata", False, str(e))

    # Test 3.4: List artifacts by task_id
    try:
        service.handle_command("save_artifact", {
            "artifact_id": "artifact-002",
            "task_id": "task-123",
            "data": {"step": 2}
        })
        result = service.handle_command("list_artifacts", {
            "task_id": "task-123"
        })
        results.add("List artifacts by task_id", result["count"] == 2)
    except Exception as e:
        results.add("List artifacts by task_id", False, str(e))

    # Test 3.5: List artifacts by process_id
    try:
        result = service.handle_command("list_artifacts", {
            "process_id": "process-456"
        })
        results.add("List artifacts by process_id", result["count"] >= 1)
    except Exception as e:
        results.add("List artifacts by process_id", False, str(e))


# =============================================================================
# 4. Error Handling Tests
# =============================================================================

def test_error_handling():
    results.set_category("4. ERROR HANDLING TESTS")

    service = create_test_service()

    # Test 4.1: Read non-existent file
    try:
        service.handle_command("read_file", {"path": "/nonexistent.txt"})
        results.add("Read non-existent file raises", False, "Should have raised")
    except FileNotFoundError:
        results.add("Read non-existent file raises FileNotFoundError", True)
    except Exception as e:
        results.add("Read non-existent file raises FileNotFoundError", False, str(type(e)))

    # Test 4.2: Delete non-existent file
    try:
        service.handle_command("delete_file", {"path": "/nonexistent.txt"})
        results.add("Delete non-existent file raises", False, "Should have raised")
    except FileNotFoundError:
        results.add("Delete non-existent file raises FileNotFoundError", True)
    except Exception as e:
        results.add("Delete non-existent file raises FileNotFoundError", False, str(type(e)))

    # Test 4.3: Get non-existent artifact
    try:
        service.handle_command("get_artifact", {"artifact_id": "nonexistent"})
        results.add("Get non-existent artifact raises", False, "Should have raised")
    except KeyError:
        results.add("Get non-existent artifact raises KeyError", True)
    except Exception as e:
        results.add("Get non-existent artifact raises KeyError", False, str(type(e)))

    # Test 4.4: Missing required parameter
    try:
        service.handle_command("save_file", {"content": "no path"})
        results.add("Missing path raises", False, "Should have raised")
    except ValueError as e:
        results.add("Missing path raises ValueError", "path" in str(e))
    except Exception as e:
        results.add("Missing path raises ValueError", False, str(type(e)))

    # Test 4.5: Unknown action
    try:
        service.handle_command("unknown_action", {})
        results.add("Unknown action raises", False, "Should have raised")
    except ValueError as e:
        results.add("Unknown action raises ValueError", "unknown_action" in str(e))
    except Exception as e:
        results.add("Unknown action raises ValueError", False, str(type(e)))


# =============================================================================
# 5. Storage Limits Tests
# =============================================================================

def test_storage_limits():
    results.set_category("5. STORAGE LIMITS TESTS")

    service = create_test_service()
    # Override limits for testing
    service._max_file_size = 100  # 100 bytes
    service._max_files = 5

    # Test 5.1: File too large
    try:
        large_content = "x" * 200  # 200 bytes > 100 limit
        service.handle_command("save_file", {
            "path": "/large.txt",
            "content": large_content
        })
        results.add("File too large rejected", False, "Should have raised")
    except ValueError as e:
        results.add("File too large rejected", "too large" in str(e).lower())
    except Exception as e:
        results.add("File too large rejected", False, str(type(e)))

    # Test 5.2: Max files limit
    try:
        # Fill up storage
        for i in range(5):
            service.handle_command("save_file", {
                "path": f"/file{i}.txt",
                "content": "x"
            })
        # Try to add one more
        service.handle_command("save_file", {
            "path": "/overflow.txt",
            "content": "x"
        })
        results.add("Max files limit enforced", False, "Should have raised")
    except ValueError as e:
        results.add("Max files limit enforced", "limit" in str(e).lower())
    except Exception as e:
        results.add("Max files limit enforced", False, str(type(e)))

    # Test 5.3: Overwrite doesn't count against limit
    try:
        service.handle_command("save_file", {
            "path": "/file0.txt",
            "content": "updated"
        })
        results.add("Overwrite doesn't count against limit", True)
    except Exception as e:
        results.add("Overwrite doesn't count against limit", False, str(e))


# =============================================================================
# 6. Content Hash Tests
# =============================================================================

def test_content_hash():
    results.set_category("6. CONTENT HASH TESTS")

    service = create_test_service()

    # Test 6.1: Save returns hash
    try:
        result = service.handle_command("save_file", {
            "path": "/hash_test.txt",
            "content": "test content"
        })
        results.add("Save returns content_hash", "content_hash" in result and len(result["content_hash"]) == 64)
    except Exception as e:
        results.add("Save returns content_hash", False, str(e))

    # Test 6.2: Same content = same hash
    try:
        result1 = service.handle_command("save_file", {
            "path": "/hash1.txt",
            "content": "identical"
        })
        result2 = service.handle_command("save_file", {
            "path": "/hash2.txt",
            "content": "identical"
        })
        results.add("Same content = same hash", result1["content_hash"] == result2["content_hash"])
    except Exception as e:
        results.add("Same content = same hash", False, str(e))

    # Test 6.3: Different content = different hash
    try:
        result1 = service.handle_command("save_file", {
            "path": "/diff1.txt",
            "content": "content A"
        })
        result2 = service.handle_command("save_file", {
            "path": "/diff2.txt",
            "content": "content B"
        })
        results.add("Different content = different hash", result1["content_hash"] != result2["content_hash"])
    except Exception as e:
        results.add("Different content = different hash", False, str(e))


# =============================================================================
# 7. Storage Stats Tests
# =============================================================================

def test_storage_stats():
    results.set_category("7. STORAGE STATS TESTS")

    service = create_test_service()

    # Add some data
    service.handle_command("save_file", {"path": "/stats/f1.txt", "content": "hello"})
    service.handle_command("save_file", {"path": "/stats/f2.txt", "content": "world"})
    service.handle_command("save_artifact", {"artifact_id": "a1", "data": {"x": 1}})

    # Test 7.1: Get stats
    try:
        result = service.handle_command("get_stats", {})
        stats = result["stats"]
        results.add("Get stats returns data", "files_count" in stats and "artifacts_count" in stats)
    except Exception as e:
        results.add("Get stats returns data", False, str(e))

    # Test 7.2: Files count
    try:
        result = service.handle_command("get_stats", {})
        results.add("Files count correct", result["stats"]["files_count"] >= 2)
    except Exception as e:
        results.add("Files count correct", False, str(e))

    # Test 7.3: Storage type is in-memory
    try:
        result = service.handle_command("get_stats", {})
        results.add("Storage type is in-memory", result["stats"]["storage_type"] == "in-memory")
    except Exception as e:
        results.add("Storage type is in-memory", False, str(e))


# =============================================================================
# 8. Overwrite Behavior Tests
# =============================================================================

def test_overwrite_behavior():
    results.set_category("8. OVERWRITE BEHAVIOR TESTS")

    service = create_test_service()

    # Test 8.1: Default overwrite allowed
    try:
        service.handle_command("save_file", {"path": "/overwrite.txt", "content": "v1"})
        service.handle_command("save_file", {"path": "/overwrite.txt", "content": "v2"})
        result = service.handle_command("read_file", {"path": "/overwrite.txt"})
        results.add("Default overwrite allowed", result["content"] == "v2")
    except Exception as e:
        results.add("Default overwrite allowed", False, str(e))

    # Test 8.2: Overwrite=False prevents overwrite
    try:
        service.handle_command("save_file", {"path": "/no_overwrite.txt", "content": "v1"})
        service.handle_command("save_file", {
            "path": "/no_overwrite.txt",
            "content": "v2",
            "overwrite": False
        })
        results.add("Overwrite=False prevents overwrite", False, "Should have raised")
    except ValueError as e:
        results.add("Overwrite=False prevents overwrite", "already exists" in str(e))
    except Exception as e:
        results.add("Overwrite=False prevents overwrite", False, str(type(e)))


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "📦" * 30)
    print("  STORAGE SERVICE TEST SUITE")
    print("📦" * 30)

    test_node_type()
    test_file_operations()
    test_artifact_operations()
    test_error_handling()
    test_storage_limits()
    test_content_hash()
    test_storage_stats()
    test_overwrite_behavior()

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
