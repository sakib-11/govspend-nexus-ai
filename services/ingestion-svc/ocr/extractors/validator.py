"""Field validation module."""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import date
import re
import logging

from ...models.extraction import ExtractedField

logger = logging.getLogger(__name__)

class FieldValidator:
    """Validate extracted fields."""
    
    def __init__(self):
        self.rules = self._initialize_rules()
        
    def _initialize_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize validation rules for each field."""
        return {
            'invoice_number': {
                'type': 'string',
                'min_length': 4,
                'max_length': 25,
                'pattern': r'^[A-Za-z0-9\-]+$',
                'required': False,
            },
            'vendor_name': {
                'type': 'string',
                'min_length': 2,
                'max_length': 50,
                'required': True,
            },
            'total_amount': {
                'type': 'numeric',
                'min_value': 0,
                'max_value': 10**12,
                'required': True,
            },
            'date': {
                'type': 'date',
                'min_year': 1900,
                'max_year': 2100,
                'required': True,
            },
            'vendor_tax_id': {
                'type': 'string',
                'min_length': 5,
                'max_length': 15,
                'required': False,
            },
        }
    
    def validate_all(self, fields: Dict[str, ExtractedField]) -> Dict[str, Any]:
        """Validate all fields."""
        errors = []
        warnings = []
        validated_fields = {}
        
        for name, field in fields.items():
            if name in self.rules:
                result = self._validate_field(field, self.rules[name])
                if result.get('errors'):
                    errors.extend(result['errors'])
                if result.get('warnings'):
                    warnings.extend(result['warnings'])
                validated_fields[name] = result
        
        return {
            'validated_fields': validated_fields,
            'errors': errors,
            'warnings': warnings,
            'is_valid': len(errors) == 0
        }
    
    def _validate_field(
        self,
        field: ExtractedField,
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a single field."""
        value = field.value
        errors = []
        warnings = []
        
        # Required check
        if rules.get('required', False) and (value is None or value == ''):
            errors.append(f"Field '{field.name}' is required but missing")
            field.validated = False
            return {'value': value, 'errors': errors, 'warnings': warnings}
        
        # Type checks
        field_type = rules.get('type', 'string')
        
        if field_type == 'string':
            if value is not None:
                value_str = str(value)
                min_len = rules.get('min_length', 0)
                max_len = rules.get('max_length', 100)
                
                if len(value_str) < min_len:
                    errors.append(
                        f"Field '{field.name}' length {len(value_str)} "
                        f"below minimum {min_len}"
                    )
                
                if len(value_str) > max_len:
                    warnings.append(
                        f"Field '{field.name}' length {len(value_str)} "
                        f"exceeds recommended maximum {max_len}"
                    )
                
                pattern = rules.get('pattern')
                if pattern and not re.match(pattern, value_str):
                    errors.append(
                        f"Field '{field.name}' value '{value_str}' "
                        f"doesn't match pattern {pattern}"
                    )
        
        elif field_type == 'numeric':
            if value is not None:
                try:
                    num_value = Decimal(str(value))
                    min_val = rules.get('min_value')
                    max_val = rules.get('max_value')
                    
                    if min_val is not None and num_value < min_val:
                        errors.append(
                            f"Field '{field.name}' value {num_value} "
                            f"below minimum {min_val}"
                        )
                    
                    if max_val is not None and num_value > max_val:
                        errors.append(
                            f"Field '{field.name}' value {num_value} "
                            f"above maximum {max_val}"
                        )
                except:
                    errors.append(f"Field '{field.name}' is not numeric: {value}")
        
        elif field_type == 'date':
            if value is not None:
                if isinstance(value, str):
                    try:
                        from datetime import datetime
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except:
                        errors.append(f"Field '{field.name}' is not a valid date: {value}")
                
                if isinstance(value, date):
                    min_year = rules.get('min_year', 1900)
                    max_year = rules.get('max_year', 2100)
                    
                    if value.year < min_year:
                        errors.append(
                            f"Field '{field.name}' year {value.year} "
                            f"below minimum {min_year}"
                        )
                    
                    if value.year > max_year:
                        errors.append(
                            f"Field '{field.name}' year {value.year} "
                            f"above maximum {max_year}"
                        )
        
        # Update field validation status
        if errors:
            field.validated = False
            field.validation_errors = errors
        else:
            field.validated = True
        
        return {
            'value': value,
            'validated': field.validated,
            'errors': errors,
            'warnings': warnings
        }

