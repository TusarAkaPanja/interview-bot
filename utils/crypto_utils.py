import os
import hashlib
import secrets
import string
import random
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class PasswordCrypto:
    @staticmethod
    def generate_salt() -> str:
        return secrets.token_hex(32)

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_password(password: str, hashed_password: str, salt: str) -> bool:
        return hashed_password == hashlib.sha256(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_random_password(length: int = 12) -> str:
        """Generate a random password with letters and digits."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def _get_encryption_key(salt: str) -> bytes:
        """Derive an encryption key from salt using PBKDF2."""
        password = os.getenv('ENCRYPTION_PASSWORD', 'default-encryption-key-change-in-production').encode()
        salt_bytes = salt.encode('utf-8')[:16]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    @staticmethod
    def encrypt_password(password: str, salt: str) -> str:
        """Encrypt a password using the salt as part of the key derivation."""
        key = PasswordCrypto._get_encryption_key(salt)
        f = Fernet(key)
        encrypted = f.encrypt(password.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    @staticmethod
    def decrypt_password(encrypted_password: str, salt: str) -> str:
        """Decrypt a password using the salt as part of the key derivation."""
        try:
            key = PasswordCrypto._get_encryption_key(salt)
            f = Fernet(key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode('utf-8'))
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt password: {str(e)}")