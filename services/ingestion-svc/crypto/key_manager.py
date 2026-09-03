"""Key management with KMS simulation."""

import os
import json
import hashlib
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class KeyManager:
    """Simulate KMS key management for development."""
    
    def __init__(self, key_file: Optional[str] = None):
        self.key_file = key_file or os.path.join(
            os.path.expanduser("~"), 
            ".govspend", 
            "kms_keys.json"
        )
        self._ensure_key_directory()
        self.keys = self._load_keys()
        self.key_rotation_days = 90
        
    def _ensure_key_directory(self):
        """Ensure key directory exists."""
        key_dir = Path(self.key_file).parent
        key_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions
        os.chmod(key_dir, 0o700)
    
    def _load_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load keys from file or create default."""
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'r') as f:
                    os.chmod(self.key_file, 0o600)
                    return json.load(f)
            except:
                pass
        
        # Create default keys
        return self._generate_default_keys()
    
    def _generate_default_keys(self) -> Dict[str, Dict[str, Any]]:
        """Generate default keys for development."""
        keys = {
            "hmac_key": {
                "id": "hmac-key-001",
                "value": base64.b64encode(os.urandom(32)).decode(),
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=self.key_rotation_days)).isoformat(),
                "algorithm": "HMAC-SHA256",
                "purpose": "tokenization"
            },
            "encryption_key": {
                "id": "enc-key-001",
                "value": base64.b64encode(os.urandom(32)).decode(),
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=self.key_rotation_days)).isoformat(),
                "algorithm": "AES-256-GCM",
                "purpose": "encryption"
            }
        }
        
        self._save_keys(keys)
        return keys
    
    def _save_keys(self, keys: Dict[str, Dict[str, Any]]):
        """Save keys to file."""
        with open(self.key_file, 'w') as f:
            json.dump(keys, f, indent=2)
        os.chmod(self.key_file, 0o600)
    
    def get_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get a key by ID."""
        return self.keys.get(key_id)
    
    def get_hmac_key(self) -> str:
        """Get the current HMAC key."""
        hmac_key = self.keys.get("hmac_key")
        if not hmac_key:
            hmac_key = self._generate_default_keys()["hmac_key"]
        return hmac_key["value"]
    
    def get_encryption_key(self) -> str:
        """Get the current encryption key."""
        enc_key = self.keys.get("encryption_key")
        if not enc_key:
            enc_key = self._generate_default_keys()["encryption_key"]
        return enc_key["value"]
    
    def rotate_hmac_key(self) -> Dict[str, Any]:
        """Rotate the HMAC key."""
        new_key = {
            "id": f"hmac-key-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "value": base64.b64encode(os.urandom(32)).decode(),
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=self.key_rotation_days)).isoformat(),
            "algorithm": "HMAC-SHA256",
            "purpose": "tokenization"
        }
        
        # Keep old key for verification of existing tokens
        old_hmac = self.keys.get("hmac_key")
        if old_hmac:
            self.keys["hmac_key_old"] = old_hmac
        
        self.keys["hmac_key"] = new_key
        self._save_keys(self.keys)
        
        logger.info(f"HMAC key rotated: {new_key['id']}")
        return new_key
    
    def key_status(self) -> Dict[str, Any]:
        """Get status of all keys."""
        status = {}
        for key_id, key_data in self.keys.items():
            created = datetime.fromisoformat(key_data["created_at"])
            expires = datetime.fromisoformat(key_data["expires_at"])
            now = datetime.now()
            
            status[key_id] = {
                "id": key_data["id"],
                "purpose": key_data["purpose"],
                "created_at": key_data["created_at"],
                "expires_at": key_data["expires_at"],
                "days_until_expiry": (expires - now).days,
                "is_expired": now > expires,
                "algorithm": key_data["algorithm"]
            }
        
        return status
    
    def health_check(self) -> bool:
        """Check if key manager is healthy."""
        try:
            keys = self._load_keys()
            return bool(keys)
        except:
            return False

# Singleton instance
_key_manager = None

def get_key_manager() -> KeyManager:
    """Get or create the key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager

