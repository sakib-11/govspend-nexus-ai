from typing import Dict, Any, Optional, Tuple
import hashlib
import base64
from services.hsm_client import HSMClient
from models.ledger import LedgerEntry, EntityType

class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""
    
    def __init__(self, hsm_client: HSMClient):
        self.hsm_client = hsm_client
        self._encryption_cache = {}
    
    async def encrypt_entity_data(
        self,
        entity_type: EntityType,
        entity_token: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Encrypt entity data for storage"""
        
        # Separate sensitive and non-sensitive data
        sensitive_fields = self._get_sensitive_fields(entity_type)
        
        encrypted_data = {}
        non_sensitive_data = {}
        
        for key, value in data.items():
            if key in sensitive_fields:
                # Encrypt sensitive fields
                encrypted = await self.hsm_client.encrypt_field(str(value))
                encrypted_data[key] = encrypted
            else:
                # Keep non-sensitive data as-is
                non_sensitive_data[key] = value
        
        return {
            "encrypted_fields": encrypted_data,
            "non_sensitive_data": non_sensitive_data
        }
    
    async def decrypt_entity_data(
        self,
        entity_type: EntityType,
        encrypted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Decrypt entity data"""
        
        decrypted_data = {}
        
        for key, value in encrypted_data.items():
            if isinstance(value, dict) and value.get("encrypted", False):
                # Decrypt field
                decrypted_value = await self.hsm_client.decrypt_field(
                    value.get("ciphertext", ""),
                    value.get("key_id", ""),
                    value.get("iv", ""),
                    value.get("auth_tag", "")
                )
                decrypted_data[key] = decrypted_value
            else:
                # Copy non-encrypted data
                decrypted_data[key] = value
        
        return decrypted_data
    
    def _get_sensitive_fields(self, entity_type: EntityType) -> list:
        """Get sensitive fields for entity type"""
        
        sensitive_fields_map = {
            EntityType.VENDOR: [
                "pan", "gst", "bank_account", "upi", "phone", "email", 
                "address", "contact_person", "registration_number"
            ],
            EntityType.OFFICIAL: [
                "aadhaar", "pan", "phone", "email", "address", 
                "bank_account", "upi"
            ],
            EntityType.USER: [
                "aadhaar", "pan", "phone", "email", "address",
                "bank_account", "upi"
            ],
            EntityType.TRANSACTION: [
                "invoice_number", "po_number", "account_number"
            ],
            EntityType.INVOICE: [
                "invoice_number", "po_number", "bank_account"
            ]
        }
        
        return sensitive_fields_map.get(entity_type, [])
    
    def generate_data_hash(self, data: Dict[str, Any]) -> str:
        """Generate hash for data integrity"""
        
        import json
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def validate_data_hash(self, data: Dict[str, Any], expected_hash: str) -> bool:
        """Validate data hash for integrity"""
        
        computed_hash = self.generate_data_hash(data)
        return computed_hash == expected_hash
