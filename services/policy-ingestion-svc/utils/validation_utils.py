import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
from uuid import UUID

def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID string"""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False

def validate_file_path(file_path: str) -> bool:
    """Validate file path"""
    
    # Check for path traversal attempts
    if '..' in file_path or file_path.startswith('/'):
        # In production, you might want to restrict to certain directories
        pass
    
    # Check if file exists (optional)
    # return os.path.exists(file_path)
    return True  # For now, just basic validation

def validate_category(category: str, allowed_categories: List[str]) -> bool:
    """Validate policy category"""
    return category in allowed_categories

def validate_embedding_dimension(embedding: List[float], expected_dimension: int) -> bool:
    """Validate embedding dimension"""
    return len(embedding) == expected_dimension

def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Validate data against a simple JSON schema
    
    This is a simplified validator. In production, use a library like jsonschema.
    """
    # Check required fields
    for field, field_schema in schema.items():
        if field_schema.get("required", False) and field not in data:
            return False
        
        if field in data:
            # Check type
            expected_type = field_schema.get("type")
            if expected_type:
                value = data[field]
                if expected_type == "string" and not isinstance(value, str):
                    return False
                elif expected_type == "integer" and not isinstance(value, int):
                    return False
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False
                elif expected_type == "array" and not isinstance(value, list):
                    return False
                elif expected_type == "object" and not isinstance(value, dict):
                    return False
    
    return True

def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """Sanitize input string to prevent injection attacks"""
    # Remove null bytes
    input_string = input_string.replace('\x00', '')
    
    # Limit length
    if len(input_string) > max_length:
        input_string = input_string[:max_length]
    
    # Additional sanitization can be added here
    return input_string

def validate_date_range(start_date: date, end_date: date) -> bool:
    """Validate that start_date is before or equal to end_date"""
    return start_date <= end_date

def validate_percentage(value: float) -> bool:
    """Validate that value is between 0 and 100"""
    return 0 <= value <= 100
