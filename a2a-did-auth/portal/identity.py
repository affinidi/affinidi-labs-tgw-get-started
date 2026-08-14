"""
did:key identity helper (Ed25519).

Generates (or loads a persisted) Ed25519 keypair and derives a did:key DID.
Also provides a helper to sign an EdDSA compact JWS for the DID Auth
challenge-response flow.
"""

import json
import os
import time
from pathlib import Path

import base58
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
)

# multicodec varint prefix for Ed25519 public key (0xed01)
MULTICODEC_ED25519_PUB = bytes([0xED, 0x01])

DEFAULT_KEY_FILE = Path(__file__).parent / "caller_identity.json"


def _public_key_to_did(raw_public: bytes) -> tuple[str, str]:
    """Returns (did, multibase_fragment)."""
    multibase_value = "z" + \
        base58.b58encode(MULTICODEC_ED25519_PUB + raw_public).decode()
    did = f"did:key:{multibase_value}"
    return did, multibase_value


class CallerIdentity:
    def __init__(self, private_key: Ed25519PrivateKey):
        self.private_key = private_key
        self.public_key: Ed25519PublicKey = private_key.public_key()
        raw_public = self.public_key.public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.did, multibase_value = _public_key_to_did(raw_public)
        self.kid = f"{self.did}#{multibase_value}"

    @classmethod
    def load_or_create(cls, key_file: Path = DEFAULT_KEY_FILE) -> "CallerIdentity":
        if key_file.exists():
            data = json.loads(key_file.read_text())
            raw_private = bytes.fromhex(data["private_key_hex"])
            private_key = Ed25519PrivateKey.from_private_bytes(raw_private)
            return cls(private_key)

        private_key = Ed25519PrivateKey.generate()
        raw_private = private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        key_file.write_text(json.dumps(
            {"private_key_hex": raw_private.hex()}, indent=2))
        os.chmod(key_file, 0o600)
        return cls(private_key)

    def sign_challenge(self, challenge: str, ttl_seconds: int = 300, aud: str | None = None) -> tuple[str, dict]:
        """Builds a compact EdDSA JWS proving control of the DID.

        Returns (jws, payload) so callers can display exactly what was signed.
        """
        now = int(time.time())
        payload = {
            "challenge": challenge,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        if aud:
            payload["aud"] = aud

        jws = jwt.encode(
            payload,
            self.private_key,
            algorithm="EdDSA",
            headers={"kid": self.kid},
        )
        return jws, payload
