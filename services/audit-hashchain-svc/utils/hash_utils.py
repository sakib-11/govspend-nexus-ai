import hashlib
import hmac
from typing import Union

def hash_sha256(data: Union[str, bytes]) -> str:
    """Compute SHA-256 hash"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def hash_sha256_list(data_list: list) -> str:
    """Compute SHA-256 hash of a list of items"""
    combined = ''.join([str(item) for item in data_list])
    return hash_sha256(combined)

def verify_hmac_sha256(message: Union[str, bytes], signature: Union[str, bytes], key: Union[str, bytes]) -> bool:
    """Verify HMAC-SHA256"""
    if isinstance(message, str):
        message = message.encode('utf-8')
    if isinstance(signature, str):
        signature = signature.encode('utf-8')
    if isinstance(key, str):
        key = key.encode('utf-8')
    
    computed = hmac.new(key, message, hashlib.sha256).digest()
    return hmac.compare_digest(computed, signature)

def hash_chain_entry(previous_hash: str, actor: str, action: str, resource: str, payload_hash: str, timestamp: str) -> str:
    """Compute hash for a hash chain entry"""
    data = f"{previous_hash}{actor}{action}{resource}{payload_hash}{timestamp}"
    return hash_sha256(data)
