"""JSON Schema definitions for LLM input and output validation."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class InputSchema(BaseModel):
    """JSON Schema for validating LLM input data."""

    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "case_id": {"type": "string", "minLength": 1},
        "transaction_id": {"type": "string", "minLength": 1},
        "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
        "risk_tier": {"type": "string", "enum": ["HIGH", "BORDERLINE", "LOW"]},
        "evidence_bundle": {"type": "object"},
        "retrieved_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "relevance": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["policy_id", "title", "content"],
            },
        },
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "detector_type": {"type": "string"},
                    "signal_value": {"type": "number", "minimum": 0, "maximum": 1},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["detector_type", "signal_value", "confidence"],
            },
        },
    })
    required: List[str] = Field(default_factory=lambda: [
        "case_id", "transaction_id", "risk_score", "risk_tier",
        "evidence_bundle", "signals",
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


class OutputSchema(BaseModel):
    """JSON Schema for validating LLM output data."""

    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=lambda: {
        "summary": {"type": "string", "minLength": 10},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "explanations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "point_number": {"type": "integer", "minimum": 1},
                    "detector_name": {"type": "string"},
                    "sentence": {"type": "string", "minLength": 10},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "policy_references": {"type": "array", "items": {"type": "string"}},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "citation_type": {"type": "string", "enum": ["evidence", "policy"]},
                                "reference_id": {"type": "string"},
                                "reference_text": {"type": "string"},
                                "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
                            },
                            "required": ["citation_type", "reference_id", "reference_text"],
                        },
                    },
                },
                "required": ["point_number", "detector_name", "sentence", "confidence"],
            },
        },
        "grounding_score": {"type": "number", "minimum": 0, "maximum": 1},
        "citations_used": {"type": "integer", "minimum": 0},
    })
    required: List[str] = Field(default_factory=lambda: [
        "summary", "confidence", "explanations", "grounding_score",
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }
