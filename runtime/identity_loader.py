"""Identity Loader

Loads and validates identity specs from JSON files.
Identities live in the /identities directory.
"""

import json
import os
import glob
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Default location for identity spec files
IDENTITIES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "identities")


class IdentityLoader:
    """Loads identity specs from JSON files and caches them in memory."""

    def __init__(self, identities_dir: str = IDENTITIES_DIR):
        self.identities_dir = os.path.abspath(identities_dir)
        self._cache: Dict[str, Any] = {}
        self._scan()

    def _scan(self):
        """Scan the identities directory and load all .json specs."""
        if not os.path.exists(self.identities_dir):
            logger.warning(f"Identities dir not found: {self.identities_dir}")
            return

        pattern = os.path.join(self.identities_dir, "*.json")
        files = glob.glob(pattern)
        for f in files:
            try:
                with open(f, "r") as fp:
                    spec = json.load(fp)
                identity_id = spec.get("identity", {}).get("id")
                if identity_id:
                    self._cache[identity_id] = spec
                    logger.info(f"Loaded identity: {identity_id}")
                else:
                    logger.warning(f"Identity spec missing id: {f}")
            except Exception as e:
                logger.error(f"Failed to load identity from {f}: {e}")

        logger.info(f"Identity loader ready: {len(self._cache)} identities loaded")

    def load(self, identity_id: str) -> Optional[Dict[str, Any]]:
        """Load an identity spec by ID. Returns None if not found."""
        # Try cache first
        if identity_id in self._cache:
            return self._cache[identity_id]

        # Try loading directly from file
        path = os.path.join(self.identities_dir, f"{identity_id}.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    spec = json.load(f)
                self._cache[identity_id] = spec
                return spec
            except Exception as e:
                logger.error(f"Failed to load {path}: {e}")

        logger.warning(f"Identity not found: {identity_id}")
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        """Return a summary list of all loaded identities."""
        result = []
        for identity_id, spec in self._cache.items():
            info = spec.get("identity", {})
            result.append({
                "id": identity_id,
                "name": info.get("name", identity_id),
                "version": info.get("version", "1.0.0"),
                "description": info.get("description", ""),
                "author": info.get("author", ""),
                "tags": spec.get("meta", {}).get("tags", [])
            })
        return result

    def reload(self):
        """Force reload all identities from disk."""
        self._cache.clear()
        self._scan()

    def load_from_dict(self, spec: Dict[str, Any]) -> Optional[str]:
        """Load an identity spec directly from a dict (e.g. from API payload)."""
        identity_id = spec.get("identity", {}).get("id")
        if not identity_id:
            return None
        self._cache[identity_id] = spec
        return identity_id

    def validate(self, spec: Dict[str, Any]) -> tuple[bool, str]:
        """Basic validation of an identity spec. Returns (valid, error_message)."""
        if "identity" not in spec:
            return False, "Missing 'identity' section"
        if not spec["identity"].get("id"):
            return False, "Missing identity.id"
        if not spec["identity"].get("name"):
            return False, "Missing identity.name"
        if "personality" not in spec:
            return False, "Missing 'personality' section"
        if not spec["personality"].get("tone"):
            return False, "Missing personality.tone"
        return True, ""
