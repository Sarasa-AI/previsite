"""Colocated tests for the Inference Runtime Foundation."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.inference.application.adapter import InferenceAdapter
from app.core.inference.application.fake_adapter import FakeInferenceAdapter
from app.core.inference.application.pipeline import InferencePipeline
from app.core.inference.application.publisher import (
    InferenceResultPublisher,
    NoOpInferenceResultPublisher,
)
from app.core.inference.application.registry import InferenceRegistry
from app.core.inference.domain.enums import InferenceStatus
from app.core.inference.domain.models import (
    INFERENCE_SCHEMA_VERSION,
    ExecutionTrace,
    InferenceExecution,
    InferenceFinding,
    InferenceRequest,
    InferenceResult,
)
from app.core.inference.infrastructure import RUNTIME_VERSION
from app.core.inference.interface.dto import CONTRACT_VERSION
from app.core.inference.interface.mappers import to_result_dto, to_result_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _request(**overrides) -> InferenceRequest:
    defaults = dict(
        execution_id="exec-001",
        session_id=1,
        product_key="retina",
        context_reference="sha256:abc123",
        requested_at=_NOW,
    )
    return InferenceRequest(**(defaults | overrides))


def _trace(**overrides) -> ExecutionTrace:
    defaults = dict(
        started_at=_NOW,
        finished_at=_NOW,
        adapter_name="fake",
        adapter_version="1.0.0",
        runtime_version=RUNTIME_VERSION,
        product_key="retina",
    )
    return ExecutionTrace(**(defaults | overrides))


def _finding(**overrides) -> InferenceFinding:
    defaults = dict(
        artifact_type="clinical_finding",
        finding_key="f001",
        title="Test finding",
        summary="A test summary.",
    )
    return InferenceFinding(**(defaults | overrides))


def _result(**overrides) -> InferenceResult:
    defaults = dict(
        execution_id="exec-001",
        status=InferenceStatus.SUCCEEDED,
        findings=(_finding(),),
        execution_trace=_trace(),
        duration=0.1,
        runtime_metadata={},
    )
    return InferenceResult(**(defaults | overrides))


# ===========================================================================
# Domain — InferenceStatus
# ===========================================================================


class TestInferenceStatus:
    def test_values_are_strings(self):
        for member in InferenceStatus:
            assert isinstance(member.value, str)

    def test_expected_members(self):
        names = {m.name for m in InferenceStatus}
        assert names == {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED"}


# ===========================================================================
# Domain — InferenceRequest validation
# ===========================================================================


class TestInferenceRequest:
    def test_create_factory(self):
        req = InferenceRequest.create(
            session_id=42,
            product_key="cbc",
            context_reference="sha256:deadbeef",
        )
        assert req.product_key == "cbc"
        assert req.session_id == 42
        assert req.execution_id  # non-empty UUID

    def test_frozen(self):
        req = _request()
        with pytest.raises(Exception):
            req.product_key = "other"  # type: ignore[misc]

    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            _request(execution_id="   ")

    def test_empty_product_key_rejected(self):
        with pytest.raises(ValueError, match="product_key"):
            _request(product_key="")

    def test_empty_context_reference_rejected(self):
        with pytest.raises(ValueError, match="context_reference"):
            _request(context_reference="  ")

    def test_non_positive_session_id_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _request(session_id=0)

    def test_negative_session_id_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _request(session_id=-5)


# ===========================================================================
# Domain — InferenceFinding (neutral artifact)
# ===========================================================================


class TestInferenceFinding:
    def test_basic_construction(self):
        f = _finding()
        assert f.artifact_type == "clinical_finding"

    def test_frozen(self):
        f = _finding()
        with pytest.raises(Exception):
            f.title = "other"  # type: ignore[misc]

    def test_empty_artifact_type_rejected(self):
        with pytest.raises(ValueError, match="artifact_type"):
            _finding(artifact_type="  ")

    def test_empty_finding_key_rejected(self):
        with pytest.raises(ValueError, match="finding_key"):
            _finding(finding_key="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError, match="title"):
            _finding(title="")

    def test_confidence_bounds(self):
        _finding(confidence=0.0)
        _finding(confidence=1.0)
        with pytest.raises(ValueError):
            _finding(confidence=1.1)
        with pytest.raises(ValueError):
            _finding(confidence=-0.1)

    def test_confidence_optional(self):
        f = _finding(confidence=None)
        assert f.confidence is None

    def test_various_artifact_types(self):
        for at in ("risk_signal", "recommendation", "quality_flag", "validation_issue"):
            f = _finding(artifact_type=at)
            assert f.artifact_type == at


# ===========================================================================
# Domain — ExecutionTrace product_key
# ===========================================================================


class TestExecutionTrace:
    def test_product_key_stored(self):
        t = _trace(product_key="ecg")
        assert t.product_key == "ecg"

    def test_empty_product_key_rejected(self):
        with pytest.raises(ValueError, match="product_key"):
            _trace(product_key="")

    def test_frozen(self):
        t = _trace()
        with pytest.raises(Exception):
            t.product_key = "other"  # type: ignore[misc]


# ===========================================================================
# Domain — InferenceResult
# ===========================================================================


class TestInferenceResult:
    def test_schema_version_constant(self):
        assert INFERENCE_SCHEMA_VERSION == "1.0.0"

    def test_frozen(self):
        r = _result()
        with pytest.raises(Exception):
            r.status = InferenceStatus.FAILED  # type: ignore[misc]

    def test_findings_tuple(self):
        r = _result()
        assert isinstance(r.findings, tuple)

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError, match="duration"):
            _result(duration=-0.001)


# ===========================================================================
# Domain — InferenceExecution lifecycle
# ===========================================================================


class TestInferenceExecution:
    def test_create_is_pending(self):
        req = _request()
        ex = InferenceExecution.create(request=req)
        assert ex.status is InferenceStatus.PENDING
        assert ex.result is None

    def test_mark_running(self):
        ex = InferenceExecution.create(request=_request())
        running = ex.mark_running()
        assert running.status is InferenceStatus.RUNNING
        assert running.result is None

    def test_complete_succeeded(self):
        ex = InferenceExecution.create(request=_request()).mark_running()
        r = _result(status=InferenceStatus.SUCCEEDED)
        done = ex.complete(r)
        assert done.status is InferenceStatus.SUCCEEDED
        assert done.result is r

    def test_complete_failed(self):
        ex = InferenceExecution.create(request=_request()).mark_running()
        r = _result(status=InferenceStatus.FAILED)
        done = ex.complete(r)
        assert done.status is InferenceStatus.FAILED

    def test_complete_skipped(self):
        ex = InferenceExecution.create(request=_request()).mark_running()
        r = _result(status=InferenceStatus.SKIPPED)
        done = ex.complete(r)
        assert done.status is InferenceStatus.SKIPPED

    def test_mark_running_from_non_pending_raises(self):
        ex = InferenceExecution.create(request=_request()).mark_running()
        with pytest.raises(ValueError, match="PENDING"):
            ex.mark_running()

    def test_complete_from_non_running_raises(self):
        ex = InferenceExecution.create(request=_request())
        with pytest.raises(ValueError, match="RUNNING"):
            ex.complete(_result())

    def test_terminal_without_result_raises(self):
        with pytest.raises(ValueError):
            InferenceExecution(
                request=_request(),
                status=InferenceStatus.SUCCEEDED,
                result=None,
            )

    def test_non_terminal_with_result_raises(self):
        with pytest.raises(ValueError):
            InferenceExecution(
                request=_request(),
                status=InferenceStatus.PENDING,
                result=_result(),
            )

    def test_immutable_transitions_return_new_objects(self):
        ex = InferenceExecution.create(request=_request())
        running = ex.mark_running()
        assert ex is not running
        done = running.complete(_result())
        assert running is not done


# ===========================================================================
# Application — InferenceRegistry
# ===========================================================================


class TestInferenceRegistry:
    def setup_method(self):
        self.registry = InferenceRegistry()

    def test_register_and_resolve(self):
        adapter = FakeInferenceAdapter()
        self.registry.register("retina", adapter)
        assert self.registry.resolve("retina") is adapter

    def test_duplicate_register_raises(self):
        self.registry.register("retina", FakeInferenceAdapter())
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register("retina", FakeInferenceAdapter())

    def test_missing_resolve_raises(self):
        with pytest.raises(KeyError, match="No adapter registered"):
            self.registry.resolve("unknown")

    def test_registered_products_immutable_tuple(self):
        self.registry.register("cbc", FakeInferenceAdapter())
        self.registry.register("retina", FakeInferenceAdapter())
        products = self.registry.registered_products()
        assert isinstance(products, tuple)
        # sorted alphabetically
        assert products == ("cbc", "retina")

    def test_registered_products_snapshot(self):
        self.registry.register("a", FakeInferenceAdapter())
        snap = self.registry.registered_products()
        self.registry.register("b", FakeInferenceAdapter())
        # snapshot is not affected by later registrations
        assert "b" not in snap

    def test_clear_removes_all(self):
        self.registry.register("retina", FakeInferenceAdapter())
        self.registry.clear()
        assert self.registry.registered_products() == ()


# ===========================================================================
# Application — Protocol satisfaction
# ===========================================================================


class TestProtocolSatisfaction:
    def test_fake_adapter_satisfies_protocol(self):
        adapter = FakeInferenceAdapter()
        assert isinstance(adapter, InferenceAdapter)

    def test_noop_publisher_satisfies_protocol(self):
        publisher = NoOpInferenceResultPublisher()
        assert isinstance(publisher, InferenceResultPublisher)


# ===========================================================================
# Application — FakeInferenceAdapter determinism
# ===========================================================================


class TestFakeInferenceAdapter:
    @pytest.mark.asyncio
    async def test_returns_succeeded(self):
        adapter = FakeInferenceAdapter()
        req = _request()
        result = await adapter.infer(req)
        assert result.status is InferenceStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_deterministic_same_input(self):
        adapter = FakeInferenceAdapter()
        req = _request(product_key="cbc", session_id=7)
        r1 = await adapter.infer(req)
        r2 = await adapter.infer(req)
        assert r1.findings[0].finding_key == r2.findings[0].finding_key

    @pytest.mark.asyncio
    async def test_different_inputs_different_keys(self):
        adapter = FakeInferenceAdapter()
        r1 = await adapter.infer(_request(product_key="cbc", session_id=1))
        r2 = await adapter.infer(_request(product_key="retina", session_id=1))
        assert r1.findings[0].finding_key != r2.findings[0].finding_key

    @pytest.mark.asyncio
    async def test_finding_artifact_type_is_clinical_finding(self):
        adapter = FakeInferenceAdapter()
        result = await adapter.infer(_request())
        assert result.findings[0].artifact_type == "clinical_finding"

    @pytest.mark.asyncio
    async def test_trace_carries_product_key(self):
        adapter = FakeInferenceAdapter()
        result = await adapter.infer(_request(product_key="ecg"))
        assert result.execution_trace.product_key == "ecg"

    def test_name_and_version(self):
        adapter = FakeInferenceAdapter()
        assert adapter.name == "fake"
        assert adapter.version == "1.0.0"


# ===========================================================================
# Application — NoOpInferenceResultPublisher
# ===========================================================================


class TestNoOpPublisher:
    @pytest.mark.asyncio
    async def test_publish_returns_none(self):
        publisher = NoOpInferenceResultPublisher()
        result = await publisher.publish(_result())
        assert result is None


# ===========================================================================
# Application — InferencePipeline
# ===========================================================================


class TestInferencePipeline:
    def _make_pipeline(self, publisher=None) -> tuple[InferencePipeline, InferenceRegistry]:
        registry = InferenceRegistry()
        registry.register("retina", FakeInferenceAdapter())
        pipeline = InferencePipeline(registry, publisher)
        return pipeline, registry

    @pytest.mark.asyncio
    async def test_happy_path(self):
        pipeline, _ = self._make_pipeline()
        req = _request(product_key="retina")
        result = await pipeline.execute(req)
        assert result.status is InferenceStatus.SUCCEEDED
        assert result.execution_id == req.execution_id

    @pytest.mark.asyncio
    async def test_trace_product_key_stamped_from_request(self):
        pipeline, _ = self._make_pipeline()
        req = _request(product_key="retina")
        result = await pipeline.execute(req)
        assert result.execution_trace.product_key == "retina"

    @pytest.mark.asyncio
    async def test_unknown_product_raises(self):
        pipeline, _ = self._make_pipeline()
        with pytest.raises(KeyError, match="No adapter registered"):
            await pipeline.execute(_request(product_key="unknown-product"))

    @pytest.mark.asyncio
    async def test_publisher_called_after_infer(self):
        published: list[InferenceResult] = []

        class CapturingPublisher:
            async def publish(self, result: InferenceResult) -> None:
                published.append(result)

        pipeline, _ = self._make_pipeline(publisher=CapturingPublisher())
        result = await pipeline.execute(_request(product_key="retina"))
        assert len(published) == 1
        assert published[0] is result

    @pytest.mark.asyncio
    async def test_default_publisher_is_noop(self):
        registry = InferenceRegistry()
        registry.register("retina", FakeInferenceAdapter())
        # No publisher argument — should not raise
        pipeline = InferencePipeline(registry)
        result = await pipeline.execute(_request(product_key="retina"))
        assert result.status is InferenceStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_adapter_exception_reraises(self):
        class BrokenAdapter:
            name = "broken"
            version = "0.0.1"

            async def infer(self, request):
                raise RuntimeError("adapter exploded")

        registry = InferenceRegistry()
        registry.register("broken", BrokenAdapter())
        pipeline = InferencePipeline(registry)
        with pytest.raises(RuntimeError, match="adapter exploded"):
            await pipeline.execute(_request(product_key="broken"))

    @pytest.mark.asyncio
    async def test_skipped_result_published(self):
        published: list[InferenceResult] = []

        class SkippingAdapter:
            name = "skipper"
            version = "1.0.0"

            async def infer(self, request: InferenceRequest) -> InferenceResult:
                return InferenceResult(
                    execution_id=request.execution_id,
                    status=InferenceStatus.SKIPPED,
                    findings=(),
                    execution_trace=ExecutionTrace(
                        started_at=request.requested_at,
                        finished_at=request.requested_at,
                        adapter_name="skipper",
                        adapter_version="1.0.0",
                        runtime_version=RUNTIME_VERSION,
                        product_key=request.product_key,
                    ),
                    duration=0.0,
                    runtime_metadata={},
                )

        class CapturingPublisher:
            async def publish(self, result: InferenceResult) -> None:
                published.append(result)

        registry = InferenceRegistry()
        registry.register("skip-product", SkippingAdapter())
        pipeline = InferencePipeline(registry, CapturingPublisher())
        result = await pipeline.execute(_request(product_key="skip-product"))
        assert result.status is InferenceStatus.SKIPPED
        assert len(published) == 1


# ===========================================================================
# Interface — DTO mapping + CONTRACT_VERSION
# ===========================================================================


class TestDTOMapping:
    def test_contract_version_constant(self):
        assert CONTRACT_VERSION == "1.0.0"

    def test_to_result_dto_status_is_string(self):
        dto = to_result_dto(_result())
        assert isinstance(dto.status, str)
        assert dto.status == "succeeded"

    def test_to_result_dto_findings_list(self):
        dto = to_result_dto(_result())
        assert isinstance(dto.findings, list)
        assert dto.findings[0].artifact_type == "clinical_finding"

    def test_to_result_dto_trace_product_key(self):
        dto = to_result_dto(_result(execution_trace=_trace(product_key="ecg")))
        assert dto.execution_trace.product_key == "ecg"

    def test_to_result_response_envelope(self):
        response = to_result_response(_result())
        assert response.contract_version == CONTRACT_VERSION
        assert response.result.execution_id == "exec-001"

    def test_timestamps_formatted_as_utc_z(self):
        dto = to_result_dto(_result())
        assert dto.execution_trace.started_at.endswith("Z")
        assert dto.execution_trace.finished_at.endswith("Z")

    def test_dto_frozen(self):
        dto = to_result_dto(_result())
        with pytest.raises(Exception):
            dto.status = "running"  # type: ignore[misc]


# ===========================================================================
# Import boundary — core.inference must not import workspace / intelligence
# ===========================================================================


class TestImportBoundary:
    def _all_inference_modules(self) -> list[str]:
        import pkgutil
        import importlib
        import app.core.inference as pkg

        modules = [pkg.__name__]
        for info in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
            if "tests" not in info.name:
                modules.append(info.name)
        return modules

    def test_no_workspace_import(self):
        import sys

        for mod_name in self._all_inference_modules():
            __import__(mod_name)

        for mod_name in sys.modules:
            if mod_name.startswith("app.core.inference"):
                src = sys.modules[mod_name].__file__ or ""
                # Walk imported modules list — none should be workspace/intelligence
                pass

        # Simpler: verify no workspace/intelligence in transitive imports
        # by inspecting each module's source for forbidden imports.
        import importlib
        import ast
        import os

        inference_root = os.path.dirname(__import__("app.core.inference", fromlist=[""]).__file__)
        forbidden = {"app.modules.workspace", "app.modules.intelligence"}

        violations = []
        for dirpath, _, filenames in os.walk(inference_root):
            if "tests" in dirpath:
                continue
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                source = open(path).read()
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        names = []
                        if isinstance(node, ast.Import):
                            names = [alias.name for alias in node.names]
                        elif node.module:
                            names = [node.module]
                        for name in names:
                            for f in forbidden:
                                if name.startswith(f):
                                    violations.append(f"{path}: imports {name}")
        assert not violations, f"Forbidden imports found:\n" + "\n".join(violations)
