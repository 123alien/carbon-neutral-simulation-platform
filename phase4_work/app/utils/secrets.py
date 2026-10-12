import base64
import hashlib
import json
import os
from cryptography.fernet import Fernet

def _fernet():
    configured=os.getenv("DATA_SOURCE_SECRET_KEY")
    key=configured.encode() if configured else base64.urlsafe_b64encode(hashlib.sha256(os.getenv("APP_SECRET_KEY", "development-only-change-me").encode()).digest())
    return Fernet(key)

def encrypt_credentials(value: dict | None):
    return _fernet().encrypt(json.dumps(value or {}).encode()).decode() if value else None

def decrypt_credentials(value: str | None):
    return json.loads(_fernet().decrypt(value.encode()).decode()) if value else {}
