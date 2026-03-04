"""Ed25519 event signing for collector → API payload integrity.

Generates a keypair on first run, persists the private key to
``~/.agentic-gov/signing.key``, and signs canonical event payloads
so the API can reject spoofed events.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

DEFAULT_KEY_DIR = Path.home() / ".agentic-gov"
PRIVATE_KEY_FILE = "signing.key"
PUBLIC_KEY_FILE = "signing.pub"


def generate_keypair(key_dir: Path | None = None) -> tuple[Ed25519PrivateKey, bytes]:
    """Generate a new Ed25519 keypair and persist to disk.

    Returns (private_key, public_key_pem_bytes).
    """
    d = key_dir or DEFAULT_KEY_DIR
    d.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()

    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.SubjectPublicKeyInfo,
    )

    priv_path = d / PRIVATE_KEY_FILE
    priv_path.write_bytes(priv_pem)
    os.chmod(str(priv_path), 0o600)

    pub_path = d / PUBLIC_KEY_FILE
    pub_path.write_bytes(pub_pem)

    logger.info("Generated new signing keypair at %s", d)
    return private_key, pub_pem


def load_signing_key(key_dir: Path | None = None) -> Ed25519PrivateKey | None:
    """Load the private signing key from disk, or None if not enrolled."""
    d = key_dir or DEFAULT_KEY_DIR
    priv_path = d / PRIVATE_KEY_FILE
    if not priv_path.exists():
        return None
    try:
        priv_pem = priv_path.read_bytes()
        key = serialization.load_pem_private_key(priv_pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            logger.error("Signing key is not Ed25519")
            return None
        return key
    except Exception as exc:
        logger.error("Failed to load signing key: %s", exc)
        return None


def load_public_key_pem(key_dir: Path | None = None) -> str | None:
    """Load the PEM-encoded public key string."""
    d = key_dir or DEFAULT_KEY_DIR
    pub_path = d / PUBLIC_KEY_FILE
    if not pub_path.exists():
        return None
    return pub_path.read_text()


def get_key_fingerprint(pub_pem: str) -> str:
    """SHA-256 fingerprint of the public key PEM."""
    return hashlib.sha256(pub_pem.encode()).hexdigest()


def _canonical_json(event: dict) -> bytes:
    """Deterministic JSON serialization for signing."""
    filtered = {k: v for k, v in event.items() if not k.startswith("_")}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode()


def sign_event(event: dict, private_key: Ed25519PrivateKey) -> str:
    """Sign the canonical event payload and return a hex-encoded signature."""
    payload = _canonical_json(event)
    signature = private_key.sign(payload)
    return signature.hex()


def verify_event_signature(
    event: dict,
    signature_hex: str,
    public_key: Ed25519PublicKey,
) -> bool:
    """Verify an event's signature. Returns True if valid."""
    try:
        payload = _canonical_json(event)
        signature = bytes.fromhex(signature_hex)
        public_key.verify(signature, payload)
        return True
    except Exception:
        return False
