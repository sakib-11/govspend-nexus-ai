"""Stream configuration."""

from typing import Dict, Any
from enum import Enum
import os

class StreamConfig:
    """Redis Stream configuration."""
    
    # Stream names
    STREAM_TX_INGESTED = "tx.ingested"
    STREAM_TX_VALIDATED = "tx.validated"
    STREAM_TX_DETECTED = "tx.detected"
    STREAM_TX_SCORED = "tx.scored"
    STREAM_TX_CANONICALIZED = "tx.canonicalized"
    STREAM_TX_ERROR = "tx.error"
    STREAM_TX_AUDIT = "tx.audit"
    
    # Stream settings
    MAX_LEN = 100000  # Maximum number of messages in stream
    TRIM_THRESHOLD = 50000  # Trim when exceeding this
    BLOCK_TIMEOUT_MS = 5000  # Consumer block timeout
    
    # Consumer groups
    CONSUMER_GROUP_DETECTION = "detection-group"
    CONSUMER_GROUP_SCORING = "scoring-group"
    CONSUMER_GROUP_EXPLANATION = "explanation-group"
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5
    
    # Stream metadata
    @classmethod
    def get_stream_metadata(cls) -> Dict[str, Any]:
        """Get metadata for all streams."""
        return {
            cls.STREAM_TX_INGESTED: {
                "description": "Newly ingested transactions",
                "consumers": [cls.CONSUMER_GROUP_DETECTION],
                "retention_days": 30
            },
            cls.STREAM_TX_VALIDATED: {
                "description": "Validated transactions",
                "consumers": [cls.CONSUMER_GROUP_SCORING],
                "retention_days": 30
            },
            cls.STREAM_TX_DETECTED: {
                "description": "Transactions with detection results",
                "consumers": [cls.CONSUMER_GROUP_EXPLANATION],
                "retention_days": 30
            },
            cls.STREAM_TX_ERROR: {
                "description": "Error events",
                "consumers": [],
                "retention_days": 7
            },
            cls.STREAM_TX_AUDIT: {
                "description": "Audit events",
                "consumers": [],
                "retention_days": 90
            }
        }
    
    @classmethod
    def get_stream_info(cls, stream_name: str) -> Dict[str, Any]:
        """Get information about a specific stream."""
        metadata = cls.get_stream_metadata()
        return metadata.get(stream_name, {})

