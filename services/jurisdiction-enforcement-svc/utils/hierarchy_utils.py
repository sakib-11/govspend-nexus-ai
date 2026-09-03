"""Utility functions for jurisdiction hierarchy operations."""

from typing import List, Set, Tuple
from models.jurisdiction import JurisdictionLevel

def validate_jurisdiction_code(code: str) -> bool:
    """Validate jurisdiction code format"""
    # Basic validation - in production would be more robust
    return len(code) >= 2 and code.isupper()

def get_jurisdiction_level_from_code(code: str) -> Optional[JurisdictionLevel]:
    """Extract jurisdiction level from code (simplified)"""
    # This is a simplified implementation
    # In production, you'd have a proper mapping
    if "FED" in code or "US" == code:
        return JurisdictionLevel.FEDERAL
    elif len(code.split("-")) == 2:
        return JurisdictionLevel.STATE
    elif len(code.split("-")) == 3:
        return JurisdictionLevel.CITY
    else:
        return JurisdictionLevel.CUSTOM

def calculate_depth_from_ancestors(ancestors: List[str]) -> int:
    """Calculate depth based on number of ancestors"""
    return len(ancestors)

def is_valid_hierarchy_operation(operation: str) -> bool:
    """Validate if operation is valid for jurisdiction hierarchy"""
    valid_operations = ["add", "remove", "move", "query"]
    return operation in valid_operations