"""Validation utilities for jurisdiction enforcement."""

from typing import List, Optional, Tuple
from models.jurisdiction import JurisdictionAccess, JurisdictionLevel, JurisdictionType

def validate_jurisdiction_access(access: str) -> bool:
    """Validate jurisdiction access level"""
    try:
        JurisdictionAccess(access)
        return True
    except ValueError:
        return False

def validate_jurisdiction_level(level: str) -> bool:
    """Validate jurisdiction level"""
    try:
        JurisdictionLevel(level)
        return True
    except ValueError:
        return False

def validate_jurisdiction_type(jtype: str) -> bool:
    """Validate jurisdiction type"""
    try:
        JurisdictionType(jtype)
        return True
    except ValueError:
        return False

def validate_access_transition(
    current_access: JurisdictionAccess,
    new_access: JurisdictionAccess
) -> bool:
    """Validate if access transition is allowed"""
    # Define allowed transitions
    # For simplicity, we'll allow most transitions in this example
    # In production, you'd have more restrictive rules
    return True

def validate_resource_jurisdiction_match(
    resource_type: str,
    jurisdiction_id: str
) -> bool:
    """Validate if resource type is appropriate for jurisdiction"""
    # In production, you'd have specific rules
    # For now, we'll allow all combinations
    return True

def sanitize_jurisdiction_input(input_str: str) -> str:
    """Sanitize jurisdiction input to prevent injection"""
    # Remove potentially dangerous characters
    # This is a basic implementation - use proper sanitization in production
    dangerous_chars = ["'", '"', ";", "--", "/*", "*/"]
    for char in dangerous_chars:
        input_str = input_str.replace(char, "")
    return input_str.strip()