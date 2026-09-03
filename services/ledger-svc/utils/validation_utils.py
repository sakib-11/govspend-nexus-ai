import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from uuid import UUID

def validate_entity_token(entity_type: str, entity_token: str) -> bool:
    """Validate entity token format"""
    # Entity tokens should be alphanumeric with hyphens and underscores
    pattern = r'^[a-zA-Z0-9_-]+$'
    if not re.match(pattern, entity_token):
        return False
    
    # Additional validation based on entity type
    if entity_type == "vendor":
        # Vendor tokens might start with VEND-
        return entity_token.startswith("VEND-")
    elif entity_type == "official":
        # Official tokens might start with OFF-
        return entity_token.startswith("OFF-")
    elif entity_type == "transaction":
        # Transaction tokens might start with TXN-
        return entity_token.startswith("TXN-")
    elif entity_type == "invoice":
        # Invoice tokens might start with INV-
        return entity_token.startswith("INV-")
    elif entity_type == "user":
        # User tokens might start with USER-
        return entity_token.startswith("USER-")
    
    return True

def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID string"""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False

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

def validate_ip_address(ip: str) -> bool:
    """Validate IP address (IPv4 or IPv6)"""
    import socket
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except socket.error:
            return False
