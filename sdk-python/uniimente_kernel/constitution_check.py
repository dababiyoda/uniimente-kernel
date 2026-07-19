"""Constitution guard: fixed values no agent can rewrite.

Extracted from DALEOBANKS ``services/constitution.py`` (kernel Phase 2)
into the kernel SDK package. The constitution file is loaded read-only.
Its hash is recorded in the decision ledger at startup and re-verified
while the system runs; a runtime mismatch means the file changed
underneath a live process (tampering or an unreviewed edit), and the
guard fails toward silence by disarming live action. Legitimate
amendments arrive through the human ceremony in
``constitution/amendment-policy.ucl`` — a human commit followed by a
restart, which records the new hash as a ledgered constitution event.

Generalization points versus the DALEOBANKS original:

- Standard library logging; kernel ``DecisionLedger`` and ``KillSwitch``.
- The default path now points at the kernel constitution directory. Organs
  pass their own path until they fully migrate. The guard can also watch
  several files at once (the kernel has five UCL files).
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Dict, List, Optional

from uniimente_kernel.ledger import DecisionLedger, KillSwitch

logger = logging.getLogger(__name__)

DEFAULT_CONSTITUTION_PATHS = [
    "constitution/constitution.ucl",
    "constitution/sovereignty.ucl",
    "constitution/participant-rights.ucl",
    "constitution/amendment-policy.ucl",
    "constitution/shutdown-policy.ucl",
]


def _hash_file(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class ConstitutionGuard:
    """Hashes constitution files at startup and detects runtime drift."""

    def __init__(
        self,
        paths: Optional[List[str]] = None,
        *,
        ledger: Optional[DecisionLedger] = None,
        kill_switch: Optional[KillSwitch] = None,
    ) -> None:
        self.paths = list(paths or DEFAULT_CONSTITUTION_PATHS)
        self.ledger = ledger or DecisionLedger()
        self.kill_switch = kill_switch or KillSwitch(ledger=self.ledger)
        self.startup_hashes: Dict[str, str] = {}

    def text(self, path: str) -> str:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def combined_hash(self) -> Optional[str]:
        """One hash over every watched file, in declared order."""
        digests = []
        for path in self.paths:
            h = _hash_file(path)
            if h is None:
                return None
            digests.append(h)
        return hashlib.sha256("".join(digests).encode("utf-8")).hexdigest()

    def load_and_record(self) -> Optional[str]:
        """Record constitution hashes at startup (the reference point)."""
        self.startup_hashes = {}
        for path in self.paths:
            h = _hash_file(path)
            if h is None:
                logger.warning("Constitution file missing at %s", path)
                self.ledger.record("constitution_missing", {"path": path})
                return None
            self.startup_hashes[path] = h
        combined = self.combined_hash()
        self.ledger.record("constitution_hash", {
            "paths": self.paths,
            "hash": combined,
        })
        return combined

    def verify(self) -> bool:
        """Re-verify at runtime; on drift, disarm and ledger the event."""
        if not self.startup_hashes:
            # Never recorded (missing file at startup): nothing to verify.
            return True
        for path, expected in self.startup_hashes.items():
            current = _hash_file(path)
            if current != expected:
                self.ledger.record("constitution_tampered", {
                    "path": path,
                    "expected": expected,
                    "found": current,
                })
                self.kill_switch.set_armed(False, reason="constitution_tampered")
                logger.critical("Constitution changed at runtime -> live action disarmed")
                return False
        return True


__all__ = ["ConstitutionGuard", "DEFAULT_CONSTITUTION_PATHS"]
