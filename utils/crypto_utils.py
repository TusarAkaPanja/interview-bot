import os
import hashlib
import secrets
import string
import random

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