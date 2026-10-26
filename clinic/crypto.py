"""
Envelope encryption for medical documents.

* Each document gets a fresh random 256-bit data-encryption key (DEK).
* The file is sealed with AES-256-GCM (authenticated encryption, NIST SP 800-38D)
  using a 96-bit random nonce; the document UUID is bound as associated data,
  so a ciphertext cannot be swapped onto another record.
* The DEK is wrapped with a key-encryption key (KEK) from DOCUMENT_MASTER_KEYS,
  again with AES-256-GCM. Only wrapped DEKs are ever stored.
* Multiple KEKs (key_id:key) allow zero-downtime key rotation: the first key
  encrypts, any listed key decrypts, and `rotate_document_keys` re-wraps DEKs.
"""
import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

NONCE_BYTES = 12


def _b64d(value: str) -> bytes:
    value = value.strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def generate_master_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")


def load_keyring() -> dict:
    """Returns an ordered {key_id: key_bytes}; first entry is the active key."""
    raw = settings.DOCUMENT_MASTER_KEYS
    ring = {}
    if raw:
        for item in raw.split(","):
            if not item.strip():
                continue
            key_id, _, encoded = item.partition(":")
            key = _b64d(encoded)
            if len(key) != 32:
                raise ImproperlyConfigured(f"Document key '{key_id}' must be 32 bytes")
            ring[key_id.strip()] = key
    if not ring:
        # Development / test fallback: derive a KEK from SECRET_KEY with HKDF-SHA256.
        derived = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=b"cha-document-kek", info=b"dev"
        ).derive(settings.SECRET_KEY.encode())
        ring["dev"] = derived
    return ring


@dataclass
class SealedFile:
    key_id: str
    wrapped_key: bytes
    nonce: bytes
    ciphertext: bytes
    sha256: str


def encrypt_bytes(data: bytes, aad: bytes) -> SealedFile:
    ring = load_keyring()
    key_id, kek = next(iter(ring.items()))
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, data, aad)
    wrap_nonce = os.urandom(NONCE_BYTES)
    wrapped = wrap_nonce + AESGCM(kek).encrypt(wrap_nonce, dek, b"cha-dek|" + aad)
    return SealedFile(key_id, wrapped, nonce, ciphertext, hashlib.sha256(data).hexdigest())


def unwrap_key(key_id: str, wrapped: bytes, aad: bytes) -> bytes:
    ring = load_keyring()
    if key_id not in ring:
        raise ImproperlyConfigured(f"Unknown document key id '{key_id}'")
    wrapped = bytes(wrapped)
    return AESGCM(ring[key_id]).decrypt(wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:], b"cha-dek|" + aad)


def wrap_key(dek: bytes, aad: bytes):
    ring = load_keyring()
    key_id, kek = next(iter(ring.items()))
    wrap_nonce = os.urandom(NONCE_BYTES)
    return key_id, wrap_nonce + AESGCM(kek).encrypt(wrap_nonce, dek, b"cha-dek|" + aad)


def decrypt_bytes(key_id: str, wrapped: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    dek = unwrap_key(key_id, wrapped, aad)
    return AESGCM(dek).decrypt(bytes(nonce), bytes(ciphertext), aad)
