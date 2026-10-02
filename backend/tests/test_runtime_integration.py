"""End-to-end integration tests: InferenceRuntime → ClinicalIntelligenceOrchestrator.

Scenario
--------
ClinicalContext (simulated via InferenceRequest)
  → FakeInferenceAdapter
  → InferenceResult
  → ClinicalIntelligenceOrchestrator
  → ClinicalFinding / RiskSignal / Recommendation
  → InMemoryFindingRepository
  → ClinicalIntelligenceResult

Also contains import-boundary assertions.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from app.core.inference.application.fake_adapter import FakeInferenceAdapter
from app.core.inference.application.pipeline import InferencePipeline
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.domain.models import InferenceRequest
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.application.in_memory import InMemoryFindingRepository
from app.modules.intelligence.application.orchestrator import (
    ClinicalIntelligenceOrchestrator,
    ClinicalIntelligenceResult,
)

PRODUCT_KEY = "previsit-test"
SESSION_ID = 99


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo():
    r = InMemoryFindingRepository()
    yield r
    r.clear()


@pytest.fixture
def registry():
    reg = InferenceRegistry()
    reg.register(PRODUCT_KEY, FakeInferenceAdapter())
    yield reg
    reg.clear()


@pytest.fixture
def pipeline(registry):
    return InferencePipeline(registry)


@pytest.fixture
def orchestrator(repo):
    service = FindingService(repo)
    return ClinicalIntelligenceOrchestrator(service)


# ---------------------------------------------------------------------------
# Full pipeline integration scenario
# ---------------------------------------------------------------------------


class TestFullPipelineIntegration:
    async def test_fake_adapter_result_is_orchestrated(self, pipeline, orchestrator, repo):
        """FakeInferenceAdapter → InferencePipeline → orchestrate → entities persisted."""
        request = InferenceRequest.create(
            session_id=SESSION_ID,
            product_key=PRODUCT_KEY,
            context_reference="ctx-ref-001",
        )
        inference_result = await pipeline.execute(request)
        orch_result = await orchestrator.orchestrate(inference_result, SESSION_ID)

        assert isinstance(orch_result, ClinicalIntelligenceResult)
        assert orch_result.execution_id == inference_result.execution_id

    async def test_fake_adapter_clinical_finding_is_persisted(self, pipeline, orchestrator, repo):
        """FakeAdapter produces clinical_finding → must appear in repository."""
        request = InferenceRequest.create(
            session_id=SESSION_ID,
            product_key=PRODUCT_KEY,
            context_reference="ctx-ref-002",
        )
        inference_result = await pipeline.execute(request)

        # FakeInferenceAdapter always produces one "clinical_finding" artifact
        assert len(inference_result.findings) == 1
        assert inference_result.findings[0].artifact_type == "clinical_finding"

        orch_result = await orchestrator.orchestrate(inference_result, SESSION_ID)

        assert len(orch_result.findings) == 1
        stored = await repo.list_findings_for_session(SESSION_ID)
        assert len(stored) == 1

    async def test_processing_summary_reflects_fake_adapter_output(
        self, pipeline, orchestrator
    ):
        request = InferenceRequest.create(
            session_id=SESSION_ID,
            product_key=PRODUCT_KEY,
            context_reference="ctx-ref-003",
        )
        inference_result = await pipeline.execute(request)
        orch_result = await orchestrator.orchestrate(inference_result, SESSION_ID)

        s = orch_result.processing_summary
        assert s.execution_id == inference_result.execution_id
        # FakeAdapter: 1 clinical_finding → 1 created_findings, 0 ignored, 0 failures
        assert s.created_findings == 1
        assert s.ignored_unknown == 0
        assert s.validation_failures == 0
        assert s.processed_count == 1

    async def test_correct_telemetry_execution_id_throughout(self, pipeline, orchestrator):
        request = InferenceRequest.create(
            session_id=SESSION_ID,
            product_key=PRODUCT_KEY,
            context_reference="ctx-ref-004",
        )
        inference_result = await pipeline.execute(request)
        orch_result = await orchestrator.orchestrate(inference_result, SESSION_ID)

        assert orch_result.execution_id == inference_result.execution_id
        assert orch_result.processing_summary.execution_id == inference_result.execution_id

    async def test_session_id_propagated_to_findings(self, pipeline, orchestrator, repo):
        request = InferenceRequest.create(
            session_id=SESSION_ID,
            product_key=PRODUCT_KEY,
            context_reference="ctx-ref-005",
        )
        inference_result = await pipeline.execute(request)
        orch_result = await orchestrator.orchestrate(inference_result, SESSION_ID)

        for finding in orch_result.findings:
            assert finding.session_id == SESSION_ID

    async def test_result_is_immutable(self, pipeline, orchestrator):
        from pydantic import ValidationError

        request = InferenceRequest.create(
            session_id=SESSION_ID,
            product_key=PRODUCT_KEY,
            context_reference="ctx-ref-006",
        )
        inference_result = await pipeline.execute(request)
        orch_result = await orchestrator.orchestrate(inference_result, SESSION_ID)

        with pytest.raises((ValidationError, TypeError)):
            orch_result.execution_id = "tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Import boundary tests  (AST-based, no imports executed)
# ---------------------------------------------------------------------------


def _collect_imports(source_root: Path) -> dict[str, list[str]]:
    """Return {file_path: [imported_module, ...]} for all .py files under source_root."""
    results: dict[str, list[str]] = {}
    for py_file in source_root.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        results[str(py_file)] = imports
    return results


def _find_backend_root() -> Path:
    here = Path(__file__).resolve()
    # climb until we find the 'app' directory sibling
    for parent in here.parents:
        candidate = parent / "app"
        if candidate.is_dir():
            return parent
    raise RuntimeError("Could not locate backend root from test file path")


BACKEND_ROOT = _find_backend_root()
INFERENCE_ROOT = BACKEND_ROOT / "app" / "core" / "inference"
INTELLIGENCE_ROOT = BACKEND_ROOT / "app" / "modules" / "intelligence"
WORKSPACE_ROOT = BACKEND_ROOT / "app" / "modules" / "workspace"


class TestImportBoundaries:
    def test_runtime_does_not_import_intelligence(self):
        """core.inference MUST NEVER import app.modules.intelligence."""
        imports_by_file = _collect_imports(INFERENCE_ROOT)
        violations = []
        for path, imports in imports_by_file.items():
            for imp in imports:
                if "app.modules.intelligence" in imp:
                    violations.append(f"{path}: imports {imp}")
        assert violations == [], (
            "Runtime boundary violated — inference imports intelligence:\n"
            + "\n".join(violations)
        )

    def test_runtime_does_not_import_workspace(self):
        """core.inference MUST NEVER import app.modules.workspace."""
        imports_by_file = _collect_imports(INFERENCE_ROOT)
        violations = []
        for path, imports in imports_by_file.items():
            for imp in imports:
                if "app.modules.workspace" in imp:
                    violations.append(f"{path}: imports {imp}")
        assert violations == [], (
            "Runtime boundary violated — inference imports workspace:\n"
            + "\n".join(violations)
        )

    def test_workspace_does_not_import_runtime(self):
        """Workspace MUST NEVER import core.inference."""
        imports_by_file = _collect_imports(WORKSPACE_ROOT)
        violations = []
        for path, imports in imports_by_file.items():
            for imp in imports:
                if "app.core.inference" in imp:
                    violations.append(f"{path}: imports {imp}")
        assert violations == [], (
            "Workspace boundary violated — workspace imports runtime:\n"
            + "\n".join(violations)
        )

    def test_interpreter_does_not_import_workspace(self):
        """ArtifactInterpreter MUST NEVER import workspace packages."""
        interpreter_file = INTELLIGENCE_ROOT / "application" / "interpreter.py"
        tree = ast.parse(interpreter_file.read_text(encoding="utf-8"))
        violations = []
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if "app.modules.workspace" in module:
                        violations.append(module)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if "app.modules.workspace" in node.module:
                    violations.append(node.module)
        assert violations == [], (
            "Interpreter imports workspace (forbidden):\n" + "\n".join(violations)
        )

    def test_intelligence_application_does_not_import_workspace(self):
        """Intelligence application layer must not import workspace."""
        app_dir = INTELLIGENCE_ROOT / "application"
        imports_by_file = _collect_imports(app_dir)
        violations = []
        for path, imports in imports_by_file.items():
            for imp in imports:
                if "app.modules.workspace" in imp:
                    violations.append(f"{path}: imports {imp}")
        assert violations == [], (
            "Intelligence application boundary violated:\n" + "\n".join(violations)
        )

    def test_orchestrator_does_not_import_workspace(self):
        """Orchestrator specifically must not import workspace packages."""
        orchestrator_file = INTELLIGENCE_ROOT / "application" / "orchestrator.py"
        tree = ast.parse(orchestrator_file.read_text(encoding="utf-8"))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "app.modules.workspace" in node.module:
                    violations.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "app.modules.workspace" in alias.name:
                        violations.append(alias.name)
        assert violations == [], (
            "Orchestrator imports workspace (forbidden):\n" + "\n".join(violations)
        )
