"""Encryption of uploaded documents with AES-256-GCM.

AES-GCM is the current standard for authenticated encryption (NIST SP 800-38D, TLS 1.3):
it hides the content AND detects any modification of the stored bytes.

The 32-byte key comes from the DOCUMENT_MASTER_KEYS environment variable
(base64, optionally prefixed with an id like "k1:"). Without it (local development)
a key is derived from SECRET_KEY.
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


def get_key():
    value = settings.DOCUMENT_KEY.split(",")[0].strip()
    if value:
        value = value.split(":")[-1]  # remove optional "k1:" prefix
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    return hashlib.sha256(settings.SECRET_KEY.encode()).digest()


def encrypt(data: bytes):
    """Returns (nonce, ciphertext). A new random 12-byte nonce is used for every file."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(get_key()).encrypt(nonce, data, None)
    return nonce, ciphertext


def decrypt(nonce: bytes, ciphertext: bytes) -> bytes:
    """Raises cryptography.exceptions.InvalidTag if the data was tampered with."""
    return AESGCM(get_key()).decrypt(bytes(nonce), bytes(ciphertext), None)
