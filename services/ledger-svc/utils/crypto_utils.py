from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import base64

def generate_salt(length: int = 16) -> bytes:
    """Generate a cryptographically secure random salt"""
    return os.urandom(length)

def derive_key(password: bytes, salt: bytes, length: int = 32, iterations: int = 100000) -> bytes:
    """Derive a key from a password using PBKDF2"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    return kdf.derive(password)

def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt data using AES-GCM
    
    Returns:
        tuple of (ciphertext, iv, auth_tag)
    """
    iv = os.urandom(12)  # GCM recommended IV length
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return ciphertext, iv, encryptor.tag

def decrypt_aes_gcm(ciphertext: bytes, key: bytes, iv: bytes, auth_tag: bytes) -> bytes:
    """Decrypt data using AES-GCM"""
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, auth_tag), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext

def hash_data(data: bytes) -> str:
    """Compute SHA-256 hash of data"""
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(data)
    return digest.finalize().hex()

def verify_hmac(message: bytes, signature: bytes, key: bytes) -> bool:
    """Verify HMAC-SHA256 signature"""
    from cryptography.hazmat.primitives import hmac
    h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
    h.update(message)
    try:
        h.verify(signature)
        return True
    except Exception:
        return False
