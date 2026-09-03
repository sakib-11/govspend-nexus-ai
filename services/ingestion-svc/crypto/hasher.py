"""Document hashing for integrity verification."""

import hashlib
import base64
import json
from typing import Union, Dict, Any, Optional
from datetime import datetime
import logging

from ..models.crypto import HashResult, DocumentHashResult, HashAlgorithm

logger = logging.getLogger(__name__)

class DocumentHasher:
    """Hash documents for integrity verification."""
    
    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256):
        self.algorithm = algorithm
        self.supported_algorithms = {
            "SHA-256": hashlib.sha256,
            "SHA-384": hashlib.sha384,
            "SHA-512": hashlib.sha512
        }
    
    def hash_document(self, content: Union[str, bytes, dict]) -> DocumentHashResult:
        """
        Hash a document for integrity verification.
        
        Args:
            content: Document content (string, bytes, or dict)
            
        Returns:
            DocumentHashResult with hash and metadata
        """
        # Convert content to bytes
        if isinstance(content, dict):
            content_bytes = json.dumps(content, sort_keys=True).encode('utf-8')
        elif isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Compute hash
        hash_obj = self.supported_algorithms[self.algorithm.value]()
        hash_obj.update(content_bytes)
        digest = hash_obj.digest()
        hex_digest = hash_obj.hexdigest()
        
        # Create result
        return DocumentHashResult(
            invoice_doc_hash=f"sha256:{hex_digest[:16]}",
            algorithm=self.algorithm.value,
            content_length=len(content_bytes),
            content_preview=self._get_preview(content_bytes),
            timestamp=datetime.now()
        )
    
    def _get_preview(self, content: bytes, max_length: int = 100) -> str:
        """Get a preview of the content."""
        try:
            preview = content[:max_length].decode('utf-8', errors='ignore')
            if len(content) > max_length:
                preview += "..."
            return preview
        except:
            return "Unable to preview content"
    
    def verify_document(self, content: Union[str, bytes, dict], expected_hash: str) -> bool:
        """
        Verify a document against an expected hash.
        
        Args:
            content: Document content
            expected_hash: Expected hash string
            
        Returns:
            True if hash matches, False otherwise
        """
        result = self.hash_document(content)
        return result.invoice_doc_hash == expected_hash
    
    def hash_canonical_transaction(self, transaction: Dict[str, Any]) -> DocumentHashResult:
        """
        Hash a canonical transaction.
        
        Args:
            transaction: Canonical transaction dict
            
        Returns:
            DocumentHashResult with hash
        """
        # Remove temporal fields before hashing for consistency
        transaction_copy = transaction.copy()
        transaction_copy.pop('created_at', None)
        transaction_copy.pop('updated_at', None)
        transaction_copy.pop('processed_at', None)
        transaction_copy.pop('timestamp', None)
        
        return self.hash_document(transaction_copy)
    
    def compute_chain_hash(self, previous_hash: str, current_hash: str) -> str:
        """
        Compute a chain hash for audit trails.
        
        Args:
            previous_hash: Previous hash in chain
            current_hash: Current hash
            
        Returns:
            Combined hash
        """
        combined = f"{previous_hash}:{current_hash}".encode('utf-8')
        hash_obj = hashlib.sha256(combined)
        return f"sha256:{hash_obj.hexdigest()}"
    
    def get_hash_algorithm(self) -> str:
        """Get the current hash algorithm."""
        return self.algorithm.value

# Singleton instance
_hasher = None

def get_hasher() -> DocumentHasher:
    """Get or create the hasher instance."""
    global _hasher
    if _hasher is None:
        _hasher = DocumentHasher()
    return _hasher

