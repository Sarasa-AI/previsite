"""Architecture boundary tests for OpenRouter inference adapter."""

from __future__ import annotations

import ast
import os
from pathlib import Path


def _find_backend_root() -> Path:
    """Locate the backend root directory."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "app"
        if candidate.is_dir():
            return parent
    raise RuntimeError("Could not locate backend root from test file path")


BACKEND_ROOT = _find_backend_root()
OPENROUTER_PROVIDER_ROOT = (
    BACKEND_ROOT / "app" / "core" / "inference" / "infrastructure" / "providers" / "openrouter"
)
INFERENCE_DOMAIN_ROOT = BACKEND_ROOT / "app" / "core" / "inference" / "domain"
INFERENCE_APP_ROOT = BACKEND_ROOT / "app" / "core" / "inference" / "application"
INTELLIGENCE_ROOT = BACKEND_ROOT / "app" / "modules" / "intelligence"
WORKSPACE_ROOT = BACKEND_ROOT / "app" / "modules" / "workspace"


def _collect_imports_from_file(file_path: Path) -> list[str]:
    """Extract all import module names from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    return imports


def _collect_imports_from_directory(directory: Path) -> dict[str, list[str]]:
    """Collect imports from all Python files in a directory recursively."""
    results = {}
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        imports = _collect_imports_from_file(py_file)
        results[str(py_file.relative_to(BACKEND_ROOT))] = imports
    return results


class TestOpenRouterArchitectureBoundaries:
    """Verify OpenRouter provider respects architectural boundaries."""

    def test_openrouter_does_not_import_intelligence(self):
        """OpenRouter provider must not import app.modules.intelligence."""
        if not OPENROUTER_PROVIDER_ROOT.exists():
            return  # Provider not yet created

        imports_by_file = _collect_imports_from_directory(OPENROUTER_PROVIDER_ROOT)
        violations = []

        for file_path, imports in imports_by_file.items():
            for imp in imports:
                if "app.modules.intelligence" in imp:
                    violations.append(f"{file_path}: imports {imp}")

        assert not violations, (
            "OpenRouter provider boundary violated — imports intelligence:\n"
            + "\n".join(violations)
        )

    def test_openrouter_does_not_import_workspace(self):
        """OpenRouter provider must not import app.modules.workspace."""
        if not OPENROUTER_PROVIDER_ROOT.exists():
            return

        imports_by_file = _collect_imports_from_directory(OPENROUTER_PROVIDER_ROOT)
        violations = []

        for file_path, imports in imports_by_file.items():
            for imp in imports:
                if "app.modules.workspace" in imp:
                    violations.append(f"{file_path}: imports {imp}")

        assert not violations, (
            "OpenRouter provider boundary violated — imports workspace:\n"
            + "\n".join(violations)
        )

    def test_openrouter_models_do_not_import_domain(self):
        """Provider-local models must not import inference domain models."""
        models_file = OPENROUTER_PROVIDER_ROOT / "models.py"
        if not models_file.exists():
            return

        imports = _collect_imports_from_file(models_file)
        violations = []

        for imp in imports:
            if "app.core.inference.domain" in imp:
                violations.append(f"models.py imports {imp}")

        assert not violations, (
            "OpenRouter models.py must not import domain models:\n" + "\n".join(violations)
        )

    def test_mapper_is_only_domain_boundary(self):
        """Only mapper.py (data mapping) and adapter.py (port impl) touch domain.

        ``mapper.py`` is the sole provider-wire → domain *data mapping* boundary.
        ``adapter.py`` implements the ``InferenceAdapter`` port, so it must build
        the domain ``InferenceResult``/``ExecutionTrace`` it is contracted to
        return — see docs/architecture/openrouter-inference-adapter.md ("Request
        Flow"). Every remaining provider module (wire models, HTTP client,
        prompts, errors) must stay domain-free.
        """
        if not OPENROUTER_PROVIDER_ROOT.exists():
            return

        imports_by_file = _collect_imports_from_directory(OPENROUTER_PROVIDER_ROOT)

        # Find files importing domain
        domain_importers = []
        for file_path, imports in imports_by_file.items():
            for imp in imports:
                if "app.core.inference.domain" in imp:
                    domain_importers.append(file_path)
                    break

        allowed = ("mapper.py", "adapter.py")
        violations = [
            f
            for f in domain_importers
            if not any(name in f for name in allowed)
        ]

        assert not violations, (
            "Only mapper.py and adapter.py may import domain models, but found:\n"
            + "\n".join(violations)
        )

    def test_provider_wire_layer_is_domain_free(self):
        """Wire transport/serialisation modules must never import domain models."""
        if not OPENROUTER_PROVIDER_ROOT.exists():
            return

        wire_modules = ("models.py", "client.py", "prompts.py", "errors.py")
        violations = []

        for module_name in wire_modules:
            module_path = OPENROUTER_PROVIDER_ROOT / module_name
            if not module_path.exists():
                continue
            for imp in _collect_imports_from_file(module_path):
                if "app.core.inference.domain" in imp:
                    violations.append(f"{module_name}: imports {imp}")

        assert not violations, (
            "Provider wire layer must remain domain-agnostic:\n" + "\n".join(violations)
        )

    def test_inference_domain_does_not_import_openrouter(self):
        """Inference domain must remain provider-agnostic."""
        if not INFERENCE_DOMAIN_ROOT.exists():
            return

        imports_by_file = _collect_imports_from_directory(INFERENCE_DOMAIN_ROOT)
        violations = []

        for file_path, imports in imports_by_file.items():
            for imp in imports:
                if "openrouter" in imp.lower():
                    violations.append(f"{file_path}: imports {imp}")

        assert not violations, (
            "Inference domain must not import OpenRouter:\n" + "\n".join(violations)
        )

    def test_inference_application_does_not_import_openrouter(self):
        """Inference application layer must remain provider-agnostic."""
        if not INFERENCE_APP_ROOT.exists():
            return

        imports_by_file = _collect_imports_from_directory(INFERENCE_APP_ROOT)
        violations = []

        for file_path, imports in imports_by_file.items():
            for imp in imports:
                if "openrouter" in imp.lower():
                    violations.append(f"{file_path}: imports {imp}")

        assert not violations, (
            "Inference application must not import OpenRouter:\n" + "\n".join(violations)
        )
