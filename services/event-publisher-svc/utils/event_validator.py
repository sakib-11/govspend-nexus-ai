import json
from typing import Dict, Any, List
from models.events import RiskEvent, EventType

class EventValidator:
    """Validate risk events before publishing"""
    
    @staticmethod
    def validate_event(event_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate event data and return (is_valid, errors)"""
        
        errors = []
        
        # Required fields
        required_fields = ['transaction_id', 'risk_score', 'risk_tier']
        for field in required_fields:
            if field not in event_data:
                errors.append(f"Missing required field: {field}")
        
        # Risk score validation
        if 'risk_score' in event_data:
            score = event_data['risk_score']
            if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
                errors.append("Risk score must be a number between 0.0 and 1.0")
        
        # Risk tier validation
        if 'risk_tier' in event_data:
            tier = event_data['risk_tier']
            if tier not in ['LOW', 'BORDERLINE', 'HIGH']:
                errors.append("Risk tier must be LOW, BORDERLINE, or HIGH")
        
        # Event type validation
        if 'event_type' in event_data:
            try:
                EventType(event_data['event_type'])
            except ValueError:
                errors.append(f"Invalid event type: {event_data['event_type']}")
        
        # Detectors validation
        if 'detectors_triggered' in event_data:
            detectors = event_data['detectors_triggered']
            if not isinstance(detectors, list):
                errors.append("Detectors triggered must be a list")
            else:
                for detector in detectors:
                    if not isinstance(detector, str):
                        errors.append("Each detector must be a string")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def sanitize_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize event data for safe processing"""
        
        # Remove any potentially dangerous fields
        sanitized = event_data.copy()
        
        # Limit string lengths
        if 'summary' in sanitized and isinstance(sanitized['summary'], str):
            sanitized['summary'] = sanitized['summary'][:500]  # 500 char limit
        
        if 'description' in sanitized and isinstance(sanitized['description'], str):
            sanitized['description'] = sanitized['description'][:2000]  # 2000 char limit
        
        # Ensure arrays are not too large
        if 'detectors_triggered' in sanitized and isinstance(sanitized['detectors_triggered'], list):
            sanitized['detectors_triggered'] = sanitized['detectors_triggered'][:20]  # Max 20 detectors
        
        if 'tags' in sanitized and isinstance(sanitized['tags'], list):
            sanitized['tags'] = sanitized['tags'][:50]  # Max 50 tags
        
        return sanitized