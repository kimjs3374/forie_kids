import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app


_ENCRYPTION_PREFIX = "aesgcm:v1:"
_NONCE_SIZE = 12


def _master_key():
    secret = (current_app.config.get("MASTER_SECRET_KEY") or "").strip()
    if not secret:
        raise ValueError("MASTER_SECRET_KEY 가 설정되지 않았습니다. .env 를 확인해주세요.")
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_sensitive_value(value):
    plaintext = str(value or "").strip()
    if not plaintext:
        return ""

    nonce = os.urandom(_NONCE_SIZE)
    encrypted = AESGCM(_master_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    token = base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
    return f"{_ENCRYPTION_PREFIX}{token}"


def decrypt_sensitive_value(value):
    token = str(value or "").strip()
    if not token:
        return ""
    if not token.startswith(_ENCRYPTION_PREFIX):
        return token

    raw = base64.urlsafe_b64decode(token[len(_ENCRYPTION_PREFIX) :].encode("ascii"))
    nonce = raw[:_NONCE_SIZE]
    ciphertext = raw[_NONCE_SIZE:]
    decrypted = AESGCM(_master_key()).decrypt(nonce, ciphertext, None)
    return decrypted.decode("utf-8")