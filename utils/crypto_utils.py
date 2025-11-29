import os
import hashlib
import secrets

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