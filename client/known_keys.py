# client/known_keys.py

import json
import hashlib
from pathlib import Path


class KnownKeys:
    def __init__(self):
        self.path = Path.home() / ".pq-messenger" / "contacts"
        self.path.mkdir(parents=True, exist_ok=True)

    def compute_fingerprint(self, public_key: bytes) -> str:
        """Human-readable fingerprint of a key."""
        hash_bytes = hashlib.sha256(public_key).digest()
        return ":".join(f"{b:02x}" for b in hash_bytes[:16])

    def is_known(self, username: str) -> bool:
        """Have we seen this user before?"""
        return (self.path / f"{username}.json").exists()

    def store_keys(self, username: str, kem_public: bytes, dsa_public: bytes):
        """Save a contact's public keys."""
        data = {
            "username": username,
            "kem_public": kem_public.hex(),
            "dsa_public": dsa_public.hex(),
            "kem_fingerprint": self.compute_fingerprint(kem_public),
            "dsa_fingerprint": self.compute_fingerprint(dsa_public),
        }
        with open(self.path / f"{username}.json", "w") as f:
            json.dump(data, f, indent=2)

    def load_keys(self, username: str) -> dict:
        """Load a contact's stored keys."""
        with open(self.path / f"{username}.json", "r") as f:
            data = json.load(f)
        return {
            "kem_public": bytes.fromhex(data["kem_public"]),
            "dsa_public": bytes.fromhex(data["dsa_public"]),
        }

    def has_key_changed(self, username: str, kem_public: bytes, dsa_public: bytes) -> bool:
        """Check if keys differ from what we stored."""
        if not self.is_known(username):
            return False
        stored = self.load_keys(username)
        return (stored["kem_public"] != kem_public or 
                stored["dsa_public"] != dsa_public)

    def get_fingerprints(self, username: str) -> dict:
        """Get stored fingerprints for a contact."""
        with open(self.path / f"{username}.json", "r") as f:
            data = json.load(f)
        return {
            "kem": data["kem_fingerprint"],
            "dsa": data["dsa_fingerprint"],
        }