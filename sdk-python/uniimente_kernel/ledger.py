"""Append-only hash-chained decision ledger, kill switch, and rate governor.

Extracted from DALEOBANKS ``services/ledger.py`` (kernel Phase 2) and
generalized behind an organ-agnostic API. Semantics are preserved exactly:
same canonical hashing, same chain verification, same fail-safe direction.
An organ adopting this module can swap it in without changing ledger files
that already exist on disk.

Generalization points versus the DALEOBANKS original:

- No organ config import. ``KillSwitch`` takes an injected ``apply`` callable
  that performs the organ-specific state change (for DALEOBANKS:
  ``update_config(LIVE=...)``). The default apply is a no-op, which keeps the
  fail-safe property: nothing goes live because a dependency was missing.
- Standard library logging only.
- ``DecisionLedger.record_decision()`` is an additive helper that shapes an
  entry payload to the kernel ``contracts/decision.schema.json`` required
  fields. The base ``record()`` path is byte-compatible with the original.

Doctrine: the ledger proves history; it does not grant authority. An entry
can be added but never silently rewritten. The kill switch fails toward
silence. The rate governor exists so a runaway loop cannot outpace human
oversight.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, UTC
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_GENESIS_HASH = "0" * 64

# One lock per ledger file so multiple DecisionLedger instances in the same
# process serialize their appends.
_PATH_LOCKS: Dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()

# Required fields for record_decision(), mirroring
# contracts/decision.schema.json (minus hashes the ledger itself supplies).
_DECISION_REQUIRED = (
    "decision_id",
    "decider",
    "legal_principal",
    "objective",
    "question",
    "options_considered",
    "chosen",
    "rationale",
    "evidence_refs",
    "policy_version",
    "reversibility",
    "authority_chain",
    "expected_outcome",
)


def _lock_for(path: str) -> threading.Lock:
    with _PATH_LOCKS_GUARD:
        if path not in _PATH_LOCKS:
            _PATH_LOCKS[path] = threading.Lock()
        return _PATH_LOCKS[path]


def default_ledger_path() -> str:
    """Resolve the ledger location (env override for tests/deployments)."""

    return os.getenv("LEDGER_PATH", os.path.join("data", "decision_ledger.jsonl"))


def _entry_hash(entry: Dict[str, Any]) -> str:
    """Hash the canonical form of an entry (everything except its own hash)."""

    material = {k: v for k, v in entry.items() if k != "hash"}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DecisionLedger:
    """Append-only hash-chained event log (JSONL, one entry per line)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or default_ledger_path()

    # ------------------------------------------------------------------ #
    # Writing
    # ------------------------------------------------------------------ #
    def record(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append an event to the chain and return the stored entry."""

        with _lock_for(self.path):
            prev_seq, prev_hash = self._tail()
            entry: Dict[str, Any] = {
                "seq": prev_seq + 1,
                "ts": datetime.now(UTC).isoformat(),
                "event": event,
                "payload": payload or {},
                "prev_hash": prev_hash,
            }
            entry["hash"] = _entry_hash(entry)

            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")
        return entry

    def record_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Append a DecisionRecord-shaped entry.

        Validates the required fields of contracts/decision.schema.json and
        binds the record into the chain (the entry hash plays the role of
        ``ledger_prev_hash`` for the next record). Raises ValueError listing
        every missing field; a partial decision is never recorded.
        """

        missing = [k for k in _DECISION_REQUIRED if k not in decision]
        if missing:
            raise ValueError(f"DecisionRecord missing required fields: {missing}")
        return self.record("decision", decision)

    # ------------------------------------------------------------------ #
    # Reading & verification
    # ------------------------------------------------------------------ #
    def entries(self) -> List[Dict[str, Any]]:
        """All entries in order. Malformed lines are surfaced as corrupt."""

        if not os.path.exists(self.path):
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"seq": None, "event": "__corrupt__", "raw": line})
        return out

    def replay(self, event: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return entries in order, optionally filtered by event type."""

        entries = self.entries()
        if event is not None:
            entries = [e for e in entries if e.get("event") == event]
        if limit is not None:
            entries = entries[-limit:]
        return entries

    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        """Verify the hash chain. Returns (ok, first_bad_seq)."""

        prev_hash = _GENESIS_HASH
        expected_seq = 1
        for entry in self.entries():
            seq = entry.get("seq")
            if entry.get("event") == "__corrupt__" or seq != expected_seq:
                return False, seq if isinstance(seq, int) else expected_seq
            if entry.get("prev_hash") != prev_hash or _entry_hash(entry) != entry.get("hash"):
                return False, seq
            prev_hash = entry["hash"]
            expected_seq += 1
        return True, None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _tail(self) -> Tuple[int, str]:
        """Sequence number and hash of the last entry on disk."""

        if not os.path.exists(self.path):
            return 0, _GENESIS_HASH
        last_line = ""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        if not last_line:
            return 0, _GENESIS_HASH
        try:
            last = json.loads(last_line)
            return int(last["seq"]), str(last["hash"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.error("Ledger tail unreadable; continuing chain from genesis marker")
            return 0, _GENESIS_HASH


class KillSwitch:
    """Ledgered authority over live external effects.

    The organ injects ``apply``: the callable that actually changes organ
    state (DALEOBANKS passes its config update). The switch always records
    the transition in the ledger. Fail-safe direction is toward silence:
    the switch starts disarmed and never arms itself.
    """

    def __init__(
        self,
        ledger: Optional[DecisionLedger] = None,
        apply: Optional[Callable[[bool], None]] = None,
        initially_armed: bool = False,
    ) -> None:
        self.ledger = ledger or DecisionLedger()
        self._apply = apply or (lambda armed: None)
        self._armed = bool(initially_armed)

    @property
    def armed(self) -> bool:
        return self._armed

    def set_armed(self, armed: bool, reason: str = "") -> None:
        if self._armed == bool(armed):
            return
        self._armed = bool(armed)
        self._apply(bool(armed))
        self.ledger.record(
            "kill_switch",
            {"armed": bool(armed), "reason": reason or "unspecified"},
        )
        logger.warning("Kill switch %s (%s)", "ARMED" if armed else "DISARMED", reason or "unspecified")


class RateGovernor:
    """Sliding-window cap on live actions per key (typically per platform)."""

    def __init__(self, max_actions: Optional[int] = None, window_seconds: int = 3600) -> None:
        if max_actions is None:
            max_actions = int(os.getenv("RATE_GOVERNOR_MAX_PER_HOUR", "30"))
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record an action attempt for ``key``; False when over the cap."""

        now = time.monotonic()
        with self._lock:
            window = self._events[key]
            while window and now - window[0] > self.window_seconds:
                window.popleft()
            if len(window) >= self.max_actions:
                return False
            window.append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            window = self._events[key]
            while window and now - window[0] > self.window_seconds:
                window.popleft()
            return max(self.max_actions - len(window), 0)


__all__ = [
    "DecisionLedger",
    "KillSwitch",
    "RateGovernor",
    "default_ledger_path",
]
