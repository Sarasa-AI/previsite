"""Canonical pipeline stage and module name constants."""

from __future__ import annotations


class PipelineModule:
    CLINICAL_CONTEXT = "clinical_context"
    SOAP = "soap"
    OCR = "ocr"
    SUMMARY = "summary"
    RAG = "rag"
    CONFLICT = "conflict"
    PMH = "pmh"
    DB = "db"
    TIMELINE = "timeline"
    INTELLIGENCE = "intelligence"
    INFERENCE = "inference"


class PipelineStage:
    CLINICAL_CONTEXT_BUILD = "clinical_context.build"
    PMH_LOAD = "pmh.load"
    SOAP_GENERATE = "soap.generate"
    SOAP_PIPELINE = "soap.pipeline"
    OCR_EXTRACT = "ocr.extract"
    SUMMARY_BUILD = "summary.build"
    RAG_RETRIEVE = "rag.retrieve"
    CONFLICT_DETECT = "conflict.detect"
    DB_PERSIST_SOAP = "db.persist_soap"
    TIMELINE_BUILD = "timeline.build"
    INTELLIGENCE_FINDING_CREATE = "intelligence.finding_create"
    INTELLIGENCE_ORCHESTRATION = "intelligence.orchestration"
    INTELLIGENCE_INTERPRETATION = "intelligence.interpretation"
    INFERENCE_EXECUTION = "inference.execution"
    INFERENCE_ADAPTER = "inference.adapter"
