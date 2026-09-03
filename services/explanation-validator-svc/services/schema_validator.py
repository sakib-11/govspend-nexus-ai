from typing import Dict, Any, List, Optional
import json
from jsonschema import validate, ValidationError
from models.validation import ValidationStatus, ExplanationValidationResult

class SchemaValidator:
    """Validate explanation against JSON schema"""
    
    def __init__(self):
        self.schema = self._load_schema()
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load validation schema"""
        return {
            "type": "object",
            "required": ["summary", "confidence", "explanations", "grounding_score"],
            "properties": {
                "summary": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 500
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "grounding_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "explanations": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "required": ["point_number", "detector_name", "sentence", "confidence"],
                        "properties": {
                            "point_number": {"type": "integer", "minimum": 1},
                            "detector_name": {"type": "string", "minLength": 1},
                            "sentence": {"type": "string", "minLength": 10},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "evidence_ids": {"type": "array", "items": {"type": "string"}},
                            "policy_references": {"type": "array", "items": {"type": "string"}},
                            "citations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["citation_type", "reference_id", "reference_text"],
                                    "properties": {
                                        "citation_type": {"type": "string", "enum": ["evidence", "policy"]},
                                        "reference_id": {"type": "string"},
                                        "reference_text": {"type": "string", "minLength": 1},
                                        "relevance_score": {"type": "number", "minimum": 0, "maximum": 1}
                                    }
                                }
                            }
                        }
                    }
                },
                "citations_used": {"type": "integer", "minimum": 0}
            }
        }
    
    async def validate_schema(
        self,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate content against schema"""
        
        errors = []
        warnings = []
        
        try:
            validate(instance=content, schema=self.schema)
        except ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
        
        # Additional validation
        if 'explanations' in content:
            for exp in content['explanations']:
                # Check point numbers are sequential
                point_num = exp.get('point_number', 0)
                if point_num < 1:
                    errors.append(f"Invalid point number: {point_num}")
                
                # Check confidence is valid
                confidence = exp.get('confidence', 0)
                if not 0 <= confidence <= 1:
                    errors.append(f"Invalid confidence value: {confidence}")
                
                # Check detector name
                detector = exp.get('detector_name', '')
                if not detector or len(detector) < 2:
                    errors.append(f"Invalid detector name: {detector}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def get_validation_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of validation result"""
        return {
            "schema_valid": result.get("is_valid", False),
            "error_count": len(result.get("errors", [])),
            "warning_count": len(result.get("warnings", [])),
            "has_critical_issues": result.get("has_critical_issues", False)
        }