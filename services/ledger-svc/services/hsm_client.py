from typing import Optional, Dict, Any, Tuple
import base64
import os
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import boto3
import json
from config import LedgerConfig

class HSMClient:
    """HSM/KMS client for key management and encryption"""
    
    def __init__(self, config: LedgerConfig):
        self.config = config
        self._key_cache = {}
        self._kms_client = None
        self._master_key = None
        
        # Initialize KMS client based on configuration
        if config.hsm_enabled:
            self._init_kms_client()
        else:
            self._init_local_hsm()
    
    def _init_kms_client(self):
        """Initialize KMS client based on provider"""
        if self.config.hsm_type == "aws_kms":
            self._kms_client = boto3.client(
                'kms',
                region_name=self.config.hsm_region,
                endpoint_url=self.config.hsm_endpoint
            )
        elif self.config.hsm_type == "azure_keyvault":
            # Implement Azure Key Vault integration
            pass
        elif self.config.hsm_type == "hashicorp_vault":
            # Implement HashiCorp Vault integration
            pass
    
    def _init_local_hsm(self):
        """Initialize local HSM for development"""
        if self.config.local_hsm_key:
            # Use provided key or generate one
            key_bytes = base64.b64decode(self.config.local_hsm_key)
            self._master_key = key_bytes
        else:
            # Generate key for development
            self._master_key = AESGCM.generate_key(bit_length=256)
    
    async def encrypt_data(
        self,
        data: Dict[str, Any],
        key_id: Optional[str] = None
    ) -> Tuple[bytes, str, bytes, bytes]:
        """Encrypt data using HSM/KMS"""
        
        # Serialize data
        data_str = json.dumps(data, sort_keys=True)
        data_bytes = data_str.encode('utf-8')
        
        # Get encryption key
        if self.config.hsm_enabled:
            key, key_id = await self._get_key_from_kms(key_id)
        else:
            key = self._master_key
            key_id = "local-dev-key"
        
        # Generate IV
        iv = os.urandom(12)
        
        # Encrypt using AES-GCM
        aesgcm = AESGCM(key)
        encrypted_bytes = aesgcm.encrypt(iv, data_bytes, None)
        # AESGCM.encrypt returns ciphertext + tag? Actually, it returns ciphertext only, and the tag is appended.
        # In AESGCM, the encrypt method returns the ciphertext with the tag appended.
        # So we split: ciphertext = encrypted_bytes[:-16], tag = encrypted_bytes[-16:]
        # But the AESGCM implementation in cryptography returns ciphertext + tag.
        # We'll follow the common practice: the tag is the last 16 bytes.
        ciphertext = encrypted_bytes[:-16]
        auth_tag = encrypted_bytes[-16:]
        
        # Compute data hash
        data_hash = hashlib.sha256(data_bytes).hexdigest()
        
        return ciphertext, key_id, iv, auth_tag, data_hash
    
    async def decrypt_data(
        self,
        ciphertext: bytes,
        key_id: str,
        iv: bytes,
        auth_tag: bytes
    ) -> Dict[str, Any]:
        """Decrypt data using HSM/KMS"""
        
        # Get decryption key
        if self.config.hsm_enabled:
            key = await self._get_key_from_kms(key_id, decrypt=True)
        else:
            key = self._master_key
        
        # Decrypt using AES-GCM
        aesgcm = AESGCM(key)
        # Combine ciphertext and tag
        encrypted_data = ciphertext + auth_tag
        decrypted_bytes = aesgcm.decrypt(iv, encrypted_data, None)
        
        # Parse JSON
        data_str = decrypted_bytes.decode('utf-8')
        data = json.loads(data_str)
        
        return data
    
    async def _get_key_from_kms(self, key_id: Optional[str] = None, decrypt: bool = False) -> Tuple[bytes, str]:
        """Get key from KMS"""
        
        if not key_id:
            key_id = self.config.master_key_id
        
        # Check cache
        cache_key = f"{key_id}:{decrypt}"
        if cache_key in self._key_cache:
            return self._key_cache[cache_key], key_id
        
        # Get key from KMS
        if self.config.hsm_type == "aws_kms":
            if decrypt:
                # For decryption, get the key material
                response = self._kms_client.decrypt(
                    CiphertextBlob=base64.b64decode(key_id)
                )
                key_material = response['Plaintext']
            else:
                # For encryption, generate a data key
                response = self._kms_client.generate_data_key(
                    KeyId=key_id,
                    KeySpec='AES_256'
                )
                key_material = response['Plaintext']
                key_id = response['KeyId']
            
            # Cache the key
            self._key_cache[cache_key] = key_material
            
            return key_material, key_id
        
        # Fallback to local key
        return self._master_key, "local-dev-key"
    
    async def rotate_key(self, old_key_id: str) -> str:
        """Rotate encryption key"""
        
        if self.config.hsm_enabled:
            # Create new key in KMS
            if self.config.hsm_type == "aws_kms":
                response = self._kms_client.create_key(
                    Description=f"Ledger key rotated from {old_key_id}",
                    KeyUsage='ENCRYPT_DECRYPT',
                    CustomerMasterKeySpec='SYMMETRIC_DEFAULT'
                )
                new_key_id = response['KeyMetadata']['KeyId']
                
                # Create alias
                self._kms_client.create_alias(
                    AliasName=f"alias/ledger-key-{new_key_id[-8:]}",
                    TargetKeyId=new_key_id
                )
                
                return new_key_id
        
        return "local-dev-key-rotated"
    
    async def encrypt_field(
        self,
        field_value: str,
        key_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Encrypt a single field value"""
        
        data = {"value": field_value}
        ciphertext, key_id, iv, auth_tag, data_hash = await self.encrypt_data(data, key_id)
        
        return {
            "encrypted": True,
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
            "key_id": key_id,
            "iv": base64.b64encode(iv).decode('utf-8'),
            "auth_tag": base64.b64encode(auth_tag).decode('utf-8'),
            "data_hash": data_hash
        }
    
    async def decrypt_field(
        self,
        ciphertext_b64: str,
        key_id: str,
        iv_b64: str,
        auth_tag_b64: str
    ) -> str:
        """Decrypt a single field value"""
        
        ciphertext = base64.b64decode(ciphertext_b64)
        iv = base64.b64decode(iv_b64)
        auth_tag = base64.b64decode(auth_tag_b64)
        
        data = await self.decrypt_data(ciphertext, key_id, iv, auth_tag)
        return data.get("value", "")
