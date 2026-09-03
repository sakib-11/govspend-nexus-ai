"""Tokenization for vendor identifiers using HMAC-SHA256."""

import hmac
import hashlib
import base64
import os
from typing import Optional, Union, Dict, Any
from datetime import datetime
import logging
import re

from ..models.crypto import TokenResult, TokenPrefix
from .key_manager import get_key_manager

logger = logging.getLogger(__name__)

class Tokenizer:
    """Tokenize identifiers using HMAC-SHA256 + Base32."""
    
    def __init__(self):
        self.key_manager = get_key_manager()
        self.hmac_key = self.key_manager.get_hmac_key()
        self.encoding = "Base32"
        self.algorithm = "HMAC-SHA256"
        self.prefix_map = {
            TokenPrefix.VENDOR: "VEND",
            TokenPrefix.TRANSACTION: "TXN",
            TokenPrefix.DOCUMENT: "DOC",
            TokenPrefix.USER: "USR",
            TokenPrefix.DEPARTMENT: "DEPT"
        }
    
    def tokenize(
        self, 
        identifier: str, 
        prefix: TokenPrefix = TokenPrefix.VENDOR,
        salt: Optional[str] = None
    ) -> TokenResult:
        """
        Tokenize an identifier using HMAC-SHA256 + Base32.
        
        Args:
            identifier: Raw identifier to tokenize
            prefix: Token prefix (VEND, TXN, etc.)
            salt: Optional salt for additional security
            
        Returns:
            TokenResult with token and metadata
        """
        if not identifier:
            raise ValueError("Identifier cannot be empty")
        
        # Clean the identifier
        cleaned_identifier = self._clean_identifier(identifier)
        
        # Generate token
        token = self._generate_token(cleaned_identifier, prefix, salt)
        
        return TokenResult(
            original_value=identifier,
            token=token,
            prefix=prefix,
            algorithm=self.algorithm,
            encoding=self.encoding,
            timestamp=datetime.now(),
            metadata={
                "cleaned_identifier": cleaned_identifier,
                "salt_used": bool(salt),
                "hmac_key_id": self.key_manager.keys.get("hmac_key", {}).get("id", "unknown")
            }
        )
    
    def _generate_token(
        self, 
        identifier: str, 
        prefix: TokenPrefix, 
        salt: Optional[str] = None
    ) -> str:
        """Generate a token from identifier."""
        # Prepare the message
        message = identifier.encode('utf-8')
        
        # Add salt if provided
        if salt:
            message = salt.encode('utf-8') + b':' + message
        
        # Compute HMAC
        hmac_key_bytes = base64.b64decode(self.hmac_key)
        hmac_obj = hmac.new(hmac_key_bytes, message, hashlib.sha256)
        digest = hmac_obj.digest()
        
        # Encode to Base32
        base32_token = base64.b32encode(digest[:10]).decode('ascii').rstrip('=')
        
        # Generate short token (first 10 characters)
        short_token = base32_token[:10].upper()
        
        # Add prefix
        prefix_str = self.prefix_map.get(prefix, "UNK")
        token = f"{prefix_str}-{short_token}"
        
        return token
    
    def _clean_identifier(self, identifier: str) -> str:
        """Clean an identifier for consistent tokenization."""
        # Remove extra whitespace
        cleaned = ' '.join(identifier.split())
        
        # Convert to lowercase for case-insensitive matching
        cleaned = cleaned.lower()
        
        # Remove special characters that might cause issues
        cleaned = re.sub(r'[^a-z0-9\s\-_.]', '', cleaned)
        
        return cleaned.strip()
    
    def detokenize(self, token: str) -> Optional[str]:
        """
        Attempt to detokenize (only possible with original mapping).
        Note: HMAC-based tokenization is one-way by design.
        This method is for reference only.
        """
        logger.warning("HMAC-based tokenization is one-way. Detokenization is not possible.")
        return None
    
    def verify_token(self, original: str, token: str, prefix: TokenPrefix) -> bool:
        """
        Verify a token against an original identifier.
        
        Args:
            original: Original identifier
            token: Token to verify
            prefix: Token prefix
            
        Returns:
            True if token matches original
        """
        try:
            # Generate a new token from the original
            result = self.tokenize(original, prefix)
            return result.token == token
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return False
    
    def batch_tokenize(
        self, 
        identifiers: list, 
        prefix: TokenPrefix = TokenPrefix.VENDOR
    ) -> Dict[str, TokenResult]:
        """
        Tokenize multiple identifiers.
        
        Args:
            identifiers: List of identifiers to tokenize
            prefix: Token prefix
            
        Returns:
            Dict mapping original identifiers to TokenResult
        """
        results = {}
        for identifier in identifiers:
            try:
                results[identifier] = self.tokenize(identifier, prefix)
            except Exception as e:
                logger.error(f"Failed to tokenize {identifier}: {str(e)}")
                results[identifier] = None
        return results
    
    def get_token_metadata(self, token: str) -> Dict[str, Any]:
        """
        Get metadata for a token (if available).
        Note: HMAC-based tokens don't store metadata by default.
        """
        return {
            "token": token,
            "algorithm": self.algorithm,
            "encoding": self.encoding,
            "prefixes": list(self.prefix_map.values()),
            "format": f"{self.algorithm}+{self.encoding}",
            "note": "HMAC-based tokens are one-way by design"
        }

# Singleton instance
_tokenizer = None

def get_tokenizer() -> Tokenizer:
    """Get or create the tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer

