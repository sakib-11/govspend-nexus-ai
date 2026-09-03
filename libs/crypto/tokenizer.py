"""HMAC-based tokenization for PII"""
import hmac
import hashlib
import base64
from typing import Optional

class Tokenizer:
    """HMAC-based tokenization - deterministic, irreversible without key"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
    
    def tokenize(self, raw_identifier: str, prefix: str = "TOKEN") -> str:
        """Generate deterministic HMAC token"""
        digest = hmac.new(
            self.secret_key,
            raw_identifier.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Shorten to 10 chars + prefix
        short = base64.b32encode(digest[:8].encode()).decode()[:10]
        return f"{prefix}-{short.upper()}"
    
    def verify_token(self, token: str, raw_identifier: str) -> bool:
        """Verify that a token matches a raw identifier"""
        expected = self.tokenize(raw_identifier, token.split("-")[0])
        return hmac.compare_digest(token, expected)
    
    @staticmethod
    def get_entity_prefix(entity_type: str) -> str:
        """Get prefix based on entity type"""
        prefixes = {
            "vendor": "VEND",
            "official": "OFF",
            "department": "DEPT",
            "tender": "TEND",
            "invoice": "INV",
            "transaction": "TXN"
        }
        return prefixes.get(entity_type.lower(), "TOKEN")
