#!/usr/bin/env python3
"""
Tests for Persistent Storage Service.

Based on: STORAGE_SPEC_v1.1.md

Tests cover:
1. Models validation (Pydantic + SQLAlchemy)
2. FileStorage operations
3. Artifact registration flow
4. Startup recovery
5. Buffer operations
6. Checksum verification
7. Storage statistics

Ready-Made Solutions tested:
- fsspec: File system abstraction
- SQLAlchemy: Database ORM
- Pydantic: Data validation
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.models import (
    ArtifactManifest,
    ArtifactContext,
    ArtifactModel,
    ArtifactStatus,
    ArtifactVisibility,
    ModelParams,
    generate_artifact_id,
    compute_checksum,
    ARTIFACT_TYPES,
)
from storage.file_storage import FileStorage
from storage.storage_service import PersistentStorageService, StorageServiceHandler


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
# Test Fixtures
# =============================================================================

class TempStorageFixture:
    """Temporary storage directories for testing."""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ai_team_test_")
        self.base_path = os.path.join(self.temp_dir, "artifacts")
        self.temp_path = os.path.join(self.temp_dir, "temp")
        self.buffer_path = os.path.join(self.temp_dir, "buffer")
        self.orphans_path = os.path.join(self.temp_dir, "orphans")
        self.db_path = os.path.join(self.temp_dir, "storage.db")

    def cleanup(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_file_storage(self) -> FileStorage:
        return FileStorage(
            base_path=self.base_path,
            temp_path=self.temp_path,
            buffer_path=self.buffer_path,
            orphans_path=self.orphans_path,
        )

    def create_storage_service(self) -> PersistentStorageService:
        return PersistentStorageService(
            db_path=self.db_path,
            base_path=self.base_path,
            temp_path=self.temp_path,
            buffer_path=self.buffer_path,
            orphans_path=self.orphans_path,
        )


# =============================================================================
# 1. Models Tests
# =============================================================================

def test_models():
    results.set_category("1. MODELS TESTS")

    # Test 1.1: Generate artifact ID
    try:
        artifact_id = generate_artifact_id()
        results.add("Generate artifact ID starts with art_", artifact_id.startswith("art_"))
    except Exception as e:
        results.add("Generate artifact ID starts with art_", False, str(e))

    # Test 1.2: Artifact ID contains valid UUID
    try:
        artifact_id = generate_artifact_id()
        uuid_part = artifact_id.replace("art_", "")
        UUID(uuid_part)  # Will raise if invalid
        results.add("Artifact ID contains valid UUID", True)
    except Exception as e:
        results.add("Artifact ID contains valid UUID", False, str(e))

    # Test 1.3: Compute checksum format
    try:
        checksum = compute_checksum(b"test content")
        results.add("Checksum format sha256:xxx", checksum.startswith("sha256:") and len(checksum) == 71)
    except Exception as e:
        results.add("Checksum format sha256:xxx", False, str(e))

    # Test 1.4: Same content = same checksum
    try:
        checksum1 = compute_checksum(b"identical")
        checksum2 = compute_checksum(b"identical")
        results.add("Same content = same checksum", checksum1 == checksum2)
    except Exception as e:
        results.add("Same content = same checksum", False, str(e))

    # Test 1.5: Different content = different checksum
    try:
        checksum1 = compute_checksum(b"content A")
        checksum2 = compute_checksum(b"content B")
        results.add("Different content = different checksum", checksum1 != checksum2)
    except Exception as e:
        results.add("Different content = different checksum", False, str(e))

    # Test 1.6: ArtifactManifest validation
    try:
        manifest = ArtifactManifest(
            id=generate_artifact_id(),
            trace_id="trace_001",
            created_by="test.agent",
            artifact_type="research_report",
            uri="file:///test.json",
            size_bytes=100,
            checksum="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            owner="test.agent",
        )
        results.add("ArtifactManifest valid creation", manifest.id.startswith("art_"))
    except Exception as e:
        results.add("ArtifactManifest valid creation", False, str(e))

    # Test 1.7: ArtifactManifest rejects invalid ID
    try:
        ArtifactManifest(
            id="invalid_id",  # Should fail pattern validation
            trace_id="trace_001",
            created_by="test.agent",
            artifact_type="research_report",
            uri="file:///test.json",
            size_bytes=100,
            checksum="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            owner="test.agent",
        )
        results.add("ArtifactManifest rejects invalid ID", False, "Should have raised")
    except Exception:
        results.add("ArtifactManifest rejects invalid ID", True)

    # Test 1.8: ArtifactContext validation
    try:
        context = ArtifactContext(
            model_name="gpt-4o-mini",
            model_params=ModelParams(temperature=0.7, max_tokens=1000),
            input_artifacts=["art_abc"],
            execution_time_ms=500,
        )
        results.add("ArtifactContext valid creation", context.model_name == "gpt-4o-mini")
    except Exception as e:
        results.add("ArtifactContext valid creation", False, str(e))

    # Test 1.9: ARTIFACT_TYPES defined
    try:
        results.add("ARTIFACT_TYPES has standard types",
                   "research_report" in ARTIFACT_TYPES and "draft" in ARTIFACT_TYPES)
    except Exception as e:
        results.add("ARTIFACT_TYPES has standard types", False, str(e))


# =============================================================================
# 2. FileStorage Tests
# =============================================================================

def test_file_storage():
    results.set_category("2. FILE STORAGE TESTS")

    fixture = TempStorageFixture()

    try:
        fs = fixture.create_file_storage()

        # Test 2.1: Directories created
        try:
            results.add("Directories created",
                       os.path.exists(fixture.base_path) and
                       os.path.exists(fixture.temp_path) and
                       os.path.exists(fixture.buffer_path))
        except Exception as e:
            results.add("Directories created", False, str(e))

        # Test 2.2: Upload to temp
        try:
            content = b"test content"
            uri = fs.upload_to_temp(content, "test.txt")
            results.add("Upload to temp returns URI", uri.startswith("file://"))
        except Exception as e:
            results.add("Upload to temp returns URI", False, str(e))

        # Test 2.3: Move to permanent
        try:
            content = b"permanent content"
            temp_uri = fs.upload_to_temp(content, "move_test.txt")
            perm_uri = fs.move_to_permanent(temp_uri, "trace_001", "final.txt")
            results.add("Move to permanent succeeds",
                       "artifacts" in perm_uri and "trace_001" in perm_uri)
        except Exception as e:
            results.add("Move to permanent succeeds", False, str(e))

        # Test 2.4: Read file
        try:
            content = b"read test"
            uri = fs.upload(content, "trace_002", "read.txt")
            read_content = fs.read(uri)
            results.add("Read file content matches", read_content == content)
        except Exception as e:
            results.add("Read file content matches", False, str(e))

        # Test 2.5: File exists check
        try:
            content = b"exists test"
            uri = fs.upload(content, "trace_003", "exists.txt")
            results.add("Exists returns True for existing", fs.exists(uri))
        except Exception as e:
            results.add("Exists returns True for existing", False, str(e))

        # Test 2.6: Exists returns False for missing
        try:
            results.add("Exists returns False for missing",
                       not fs.exists("file:///nonexistent"))
        except Exception as e:
            results.add("Exists returns False for missing", False, str(e))

        # Test 2.7: Delete file
        try:
            content = b"delete test"
            uri = fs.upload(content, "trace_004", "delete.txt")
            deleted = fs.delete(uri)
            results.add("Delete returns True and removes file",
                       deleted and not fs.exists(uri))
        except Exception as e:
            results.add("Delete returns True and removes file", False, str(e))

        # Test 2.8: Get file size
        try:
            content = b"size test - 20 bytes"
            uri = fs.upload(content, "trace_005", "size.txt")
            size = fs.get_size(uri)
            results.add("Get size returns correct value", size == len(content))
        except Exception as e:
            results.add("Get size returns correct value", False, str(e))

        # Test 2.9: Compute checksum
        try:
            content = b"checksum test"
            checksum = fs.compute_checksum(content)
            results.add("Compute checksum format",
                       checksum.startswith("sha256:") and len(checksum) == 71)
        except Exception as e:
            results.add("Compute checksum format", False, str(e))

        # Test 2.10: Verify checksum
        try:
            content = b"verify test"
            uri = fs.upload(content, "trace_006", "verify.txt")
            checksum = fs.compute_checksum(content)
            results.add("Verify checksum succeeds", fs.verify_checksum(uri, checksum))
        except Exception as e:
            results.add("Verify checksum succeeds", False, str(e))

        # Test 2.11: Buffer artifact
        try:
            artifact_id = generate_artifact_id()
            content = b"buffered content"
            manifest_json = '{"id": "' + artifact_id + '"}'
            uri = fs.buffer_artifact(artifact_id, content, manifest_json)
            results.add("Buffer artifact creates directory",
                       os.path.exists(uri.replace("file://", "")))
        except Exception as e:
            results.add("Buffer artifact creates directory", False, str(e))

        # Test 2.12: List buffered artifacts
        try:
            buffered = fs.list_buffered_artifacts()
            results.add("List buffered artifacts returns list",
                       isinstance(buffered, list) and len(buffered) >= 1)
        except Exception as e:
            results.add("List buffered artifacts returns list", False, str(e))

        # Test 2.13: Get stats
        try:
            stats = fs.get_stats()
            results.add("Get stats returns dict with keys",
                       "artifacts" in stats and "storage_type" in stats)
        except Exception as e:
            results.add("Get stats returns dict with keys", False, str(e))

    finally:
        fixture.cleanup()


# =============================================================================
# 3. Artifact Registration Tests
# =============================================================================

def test_artifact_registration():
    results.set_category("3. ARTIFACT REGISTRATION TESTS")

    fixture = TempStorageFixture()

    try:
        storage = fixture.create_storage_service()

        # Test 3.1: Register artifact
        try:
            content = b'{"result": "success"}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="research_report",
                trace_id="trace_reg_001",
                created_by="test.agent",
                filename="result.json",
            )
            results.add("Register artifact returns manifest",
                       manifest.id.startswith("art_"))
        except Exception as e:
            results.add("Register artifact returns manifest", False, str(e))

        # Test 3.2: Manifest has correct status
        try:
            content = b'{"step": 1}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="intermediate",
                trace_id="trace_reg_002",
                created_by="test.agent",
                filename="step1.json",
            )
            results.add("Manifest status is completed", manifest.status == "completed")
        except Exception as e:
            results.add("Manifest status is completed", False, str(e))

        # Test 3.3: Manifest has checksum
        try:
            content = b'{"data": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_reg_003",
                created_by="test.agent",
                filename="log.json",
            )
            results.add("Manifest has valid checksum",
                       manifest.checksum.startswith("sha256:"))
        except Exception as e:
            results.add("Manifest has valid checksum", False, str(e))

        # Test 3.4: Manifest has permanent URI
        try:
            content = b'{"final": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="final",
                trace_id="trace_reg_004",
                created_by="test.agent",
                filename="final.json",
            )
            results.add("Manifest has permanent URI",
                       "artifacts" in manifest.uri and "trace_reg_004" in manifest.uri)
        except Exception as e:
            results.add("Manifest has permanent URI", False, str(e))

        # Test 3.5: Get artifact by ID
        try:
            content = b'{"fetch": true}'
            registered = storage.register_artifact(
                content=content,
                artifact_type="draft",
                trace_id="trace_reg_005",
                created_by="test.agent",
                filename="draft.json",
            )
            fetched = storage.get_artifact(registered.id)
            results.add("Get artifact returns manifest",
                       fetched is not None and fetched.id == registered.id)
        except Exception as e:
            results.add("Get artifact returns manifest", False, str(e))

        # Test 3.6: Get artifact content
        try:
            content = b'{"content_test": 123}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="idea",
                trace_id="trace_reg_006",
                created_by="test.agent",
                filename="idea.json",
            )
            fetched_content = storage.get_artifact_content(manifest.id)
            results.add("Get artifact content matches", fetched_content == content)
        except Exception as e:
            results.add("Get artifact content matches", False, str(e))

        # Test 3.7: List artifacts by trace_id
        try:
            # Create multiple artifacts for same trace
            for i in range(3):
                storage.register_artifact(
                    content=f'{{"item": {i}}}'.encode(),
                    artifact_type="log",
                    trace_id="trace_list_001",
                    created_by="test.agent",
                    filename=f"log_{i}.json",
                )
            artifacts = storage.list_artifacts(trace_id="trace_list_001")
            results.add("List by trace_id returns correct count", len(artifacts) == 3)
        except Exception as e:
            results.add("List by trace_id returns correct count", False, str(e))

        # Test 3.8: Register with AI context
        try:
            content = b'{"ai_generated": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="research_report",
                trace_id="trace_reg_007",
                created_by="ai.researcher",
                filename="research.json",
                context={
                    "model_name": "gpt-4o-mini",
                    "execution_time_ms": 1500,
                },
            )
            results.add("Register with context stores context",
                       manifest.context is not None and
                       manifest.context.model_name == "gpt-4o-mini")
        except Exception as e:
            results.add("Register with context stores context", False, str(e))

    finally:
        fixture.cleanup()


# =============================================================================
# 4. Checksum Verification Tests
# =============================================================================

def test_checksum_verification():
    results.set_category("4. CHECKSUM VERIFICATION TESTS")

    fixture = TempStorageFixture()

    try:
        storage = fixture.create_storage_service()

        # Test 4.1: Verify artifact returns True for valid
        try:
            content = b'{"verify": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_verify_001",
                created_by="test.agent",
                filename="verify.json",
            )
            is_valid = storage.verify_artifact(manifest.id)
            results.add("Verify artifact returns True for valid", is_valid)
        except Exception as e:
            results.add("Verify artifact returns True for valid", False, str(e))

        # Test 4.2: Verify fails for corrupted file
        try:
            content = b'{"corrupt_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_verify_002",
                created_by="test.agent",
                filename="corrupt.json",
            )
            # Corrupt the file
            file_path = manifest.uri.replace("file://", "")
            with open(file_path, "wb") as f:
                f.write(b"corrupted data")

            is_valid = storage.verify_artifact(manifest.id)
            results.add("Verify fails for corrupted file", not is_valid)
        except Exception as e:
            results.add("Verify fails for corrupted file", False, str(e))

    finally:
        fixture.cleanup()


# =============================================================================
# 5. Cleanup Operations Tests
# =============================================================================

def test_cleanup_operations():
    results.set_category("5. CLEANUP OPERATIONS TESTS")

    fixture = TempStorageFixture()

    try:
        storage = fixture.create_storage_service()

        # Test 5.1: Delete artifact
        try:
            content = b'{"delete_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_delete_001",
                created_by="test.agent",
                filename="delete.json",
            )
            deleted = storage.delete_artifact(manifest.id)
            after = storage.get_artifact(manifest.id)
            results.add("Delete artifact removes from DB", deleted and after is None)
        except Exception as e:
            results.add("Delete artifact removes from DB", False, str(e))

        # Test 5.2: Delete moves file to orphans
        try:
            content = b'{"orphan_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_delete_002",
                created_by="test.agent",
                filename="orphan.json",
            )
            storage.delete_artifact(manifest.id)
            # Check orphans directory has files
            orphan_files = list(Path(fixture.orphans_path).glob("*"))
            results.add("Delete moves file to orphans", len(orphan_files) >= 1)
        except Exception as e:
            results.add("Delete moves file to orphans", False, str(e))

        # Test 5.3: Delete non-existent returns False
        try:
            deleted = storage.delete_artifact("art_00000000-0000-0000-0000-000000000000")
            results.add("Delete non-existent returns False", not deleted)
        except Exception as e:
            results.add("Delete non-existent returns False", False, str(e))

    finally:
        fixture.cleanup()


# =============================================================================
# 6. Statistics Tests
# =============================================================================

def test_statistics():
    results.set_category("6. STATISTICS TESTS")

    fixture = TempStorageFixture()

    try:
        storage = fixture.create_storage_service()

        # Create some artifacts
        for i in range(5):
            storage.register_artifact(
                content=f'{{"item": {i}}}'.encode(),
                artifact_type="log",
                trace_id="trace_stats",
                created_by="test.agent",
                filename=f"item_{i}.json",
            )

        # Test 6.1: Get stats returns dict
        try:
            stats = storage.get_stats()
            results.add("Get stats returns dict", isinstance(stats, dict))
        except Exception as e:
            results.add("Get stats returns dict", False, str(e))

        # Test 6.2: Stats has artifact counts
        try:
            stats = storage.get_stats()
            results.add("Stats has artifact counts",
                       stats["artifacts"]["total"] >= 5)
        except Exception as e:
            results.add("Stats has artifact counts", False, str(e))

        # Test 6.3: Stats shows completed status
        try:
            stats = storage.get_stats()
            results.add("Stats shows completed count",
                       stats["artifacts"]["completed"] >= 5)
        except Exception as e:
            results.add("Stats shows completed count", False, str(e))

        # Test 6.4: Stats has storage type
        try:
            stats = storage.get_stats()
            results.add("Stats has storage type",
                       stats["storage_type"] == "persistent_sqlite_fsspec")
        except Exception as e:
            results.add("Stats has storage type", False, str(e))

    finally:
        fixture.cleanup()


# =============================================================================
# 7. Handler Tests
# =============================================================================

def test_handler():
    results.set_category("7. HANDLER TESTS")

    fixture = TempStorageFixture()

    try:
        storage = fixture.create_storage_service()
        handler = StorageServiceHandler(storage)

        # Test 7.1: Register artifact via handler
        try:
            import base64
            content = base64.b64encode(b'{"handler_test": true}').decode()
            result = handler.handle_command("register_artifact", {
                "content": content,
                "artifact_type": "log",
                "trace_id": "trace_handler_001",
                "created_by": "test.agent",
                "filename": "handler.json",
            })
            results.add("Handler register_artifact works",
                       result["status"] == "completed" and
                       result["artifact_id"].startswith("art_"))
        except Exception as e:
            results.add("Handler register_artifact works", False, str(e))

        # Test 7.2: Get artifact via handler
        try:
            import base64
            content = base64.b64encode(b'{"get_test": true}').decode()
            reg_result = handler.handle_command("register_artifact", {
                "content": content,
                "artifact_type": "log",
                "trace_id": "trace_handler_002",
                "created_by": "test.agent",
                "filename": "get.json",
            })
            get_result = handler.handle_command("get_artifact", {
                "artifact_id": reg_result["artifact_id"],
            })
            results.add("Handler get_artifact works",
                       get_result["status"] == "completed")
        except Exception as e:
            results.add("Handler get_artifact works", False, str(e))

        # Test 7.3: List artifacts via handler
        try:
            result = handler.handle_command("list_artifacts", {
                "trace_id": "trace_handler_001",
            })
            results.add("Handler list_artifacts works",
                       result["status"] == "completed" and
                       result["count"] >= 1)
        except Exception as e:
            results.add("Handler list_artifacts works", False, str(e))

        # Test 7.4: Get stats via handler
        try:
            result = handler.handle_command("get_stats", {})
            results.add("Handler get_stats works",
                       result["status"] == "completed" and
                       "stats" in result)
        except Exception as e:
            results.add("Handler get_stats works", False, str(e))

        # Test 7.5: Unknown action raises ValueError
        try:
            handler.handle_command("unknown_action", {})
            results.add("Handler unknown action raises", False, "Should have raised")
        except ValueError:
            results.add("Handler unknown action raises ValueError", True)
        except Exception as e:
            results.add("Handler unknown action raises ValueError", False, str(type(e)))

        # Test 7.6: Missing parameter raises ValueError
        try:
            handler.handle_command("register_artifact", {})
            results.add("Handler missing param raises", False, "Should have raised")
        except ValueError:
            results.add("Handler missing param raises ValueError", True)
        except Exception as e:
            results.add("Handler missing param raises ValueError", False, str(type(e)))

    finally:
        fixture.cleanup()


# =============================================================================
# 8. SQLAlchemy Model Tests
# =============================================================================

def test_sqlalchemy_models():
    results.set_category("8. SQLALCHEMY MODEL TESTS")

    fixture = TempStorageFixture()

    try:
        storage = fixture.create_storage_service()

        # Test 8.1: Model to manifest conversion
        try:
            content = b'{"conversion_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_sql_001",
                created_by="test.agent",
                filename="convert.json",
            )
            # Fetch and verify conversion works
            fetched = storage.get_artifact(manifest.id)
            results.add("Model to manifest conversion works",
                       fetched.id == manifest.id and
                       fetched.trace_id == "trace_sql_001")
        except Exception as e:
            results.add("Model to manifest conversion works", False, str(e))

        # Test 8.2: Status enum handling
        try:
            content = b'{"status_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_sql_002",
                created_by="test.agent",
                filename="status.json",
            )
            fetched = storage.get_artifact(manifest.id)
            results.add("Status enum serialization works",
                       fetched.status == "completed")
        except Exception as e:
            results.add("Status enum serialization works", False, str(e))

        # Test 8.3: Visibility enum handling
        try:
            content = b'{"visibility_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="log",
                trace_id="trace_sql_003",
                created_by="test.agent",
                filename="visibility.json",
                visibility="private",
            )
            fetched = storage.get_artifact(manifest.id)
            results.add("Visibility enum serialization works",
                       fetched.visibility == "private")
        except Exception as e:
            results.add("Visibility enum serialization works", False, str(e))

        # Test 8.4: Context JSON field handling
        try:
            content = b'{"context_test": true}'
            manifest = storage.register_artifact(
                content=content,
                artifact_type="research_report",
                trace_id="trace_sql_004",
                created_by="ai.agent",
                filename="context.json",
                context={
                    "model_name": "gpt-4",
                    "model_params": {"temperature": 0.5},
                    "execution_time_ms": 2000,
                },
            )
            fetched = storage.get_artifact(manifest.id)
            results.add("Context JSON field works",
                       fetched.context is not None and
                       fetched.context.model_name == "gpt-4" and
                       fetched.context.model_params.temperature == 0.5)
        except Exception as e:
            results.add("Context JSON field works", False, str(e))

    finally:
        fixture.cleanup()


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "🗄️" * 30)
    print("  PERSISTENT STORAGE TEST SUITE")
    print("  Based on: STORAGE_SPEC_v1.1.md")
    print("🗄️" * 30)

    test_models()
    test_file_storage()
    test_artifact_registration()
    test_checksum_verification()
    test_cleanup_operations()
    test_statistics()
    test_handler()
    test_sqlalchemy_models()

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
