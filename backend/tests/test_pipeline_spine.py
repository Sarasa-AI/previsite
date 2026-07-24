"""Regression: SOAP generation must go through soap_task + ClinicalContextBuilder."""

from pathlib import Path


def test_api_modules_do_not_import_soap_generator_directly() -> None:
    api_root = Path(__file__).resolve().parents[1] / "app" / "api"
    violators: list[str] = []
    for path in api_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "soap_generator" in text:
            violators.append(str(path.relative_to(api_root.parent.parent)))
    assert violators == [], (
        "API modules must not call soap_generator directly; "
        f"use soap_task instead. Found: {violators}"
    )


def test_soap_task_is_sole_production_orchestrator() -> None:
    from app.services import soap_task
    from app.services.clinical_context_builder import clinical_context_builder
    from app.services.soap_generator import soap_generator

    assert soap_task.clinical_context_builder is clinical_context_builder
    assert soap_task.soap_generator is soap_generator
    assert hasattr(soap_task, "run_soap_generation")
    assert hasattr(soap_task, "trigger_soap_generation")


def test_dead_document_analyzers_removed() -> None:
    services = Path(__file__).resolve().parents[1] / "app" / "services"
    assert not (services / "medical_file_analyzer.py").exists()
    assert not (services / "medical_extractor.py").exists()
