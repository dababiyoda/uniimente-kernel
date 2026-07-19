"""Raw evidence vault: the untouched original of everything sensed.

Extracted from DALEOBANKS ``services/raw_vault.py`` (kernel Phase 2) and
generalized. The sanitizer must never destroy the source record. Raw
external content is preserved here verbatim with provenance for audit and
replay, while only sanitized, delimited, evidence-only context may ever
enter a prompt. Append-only JSONL, separate from the tamper-evident
decision ledger (which stores metadata, not private text).

Generalization points versus the DALEOBANKS original:

- Standard library logging only.
- Every record now carries a ``content_hash`` (sha256 of the verbatim text),
  aligning the vault with ``contracts/evidence.schema.json``
  (``raw_content_hash``). Additive only: records written by the DALEOBANKS
  version remain readable, they simply predate the hash field.

Doctrine: raw content is preserved, not reasoned over. Instruction-shaped
content found here is quarantined data, never an instruction. A webpage
never instructs an agent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def default_vault_path() -> str:
    return os.getenv("RAW_VAULT_PATH", os.path.join("data", "raw_vault.jsonl"))


def _content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class RawVault:
    """Append-only store of raw sensed content, keyed for replay."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or default_vault_path()
        self._lock = threading.Lock()

    def deposit(
        self,
        *,
        source: str,
        text: str,
        raw_ref: str = "",
        actor: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        instruction_shaped: bool = False,
    ) -> Optional[str]:
        """Store one raw record verbatim. Returns the vault id (None on failure).

        ``instruction_shaped`` marks records whose content attempts to issue
        instructions. The flag is preserved as data for the quarantine
        pipeline; it changes nothing about storage. Raw is raw.
        """
        record = {
            "vault_id": str(uuid.uuid4()),
            "source": source,
            "raw_ref": str(raw_ref or ""),
            "actor": actor,
            "text": text,
            "content_hash": _content_hash(text),
            "received_at": datetime.now(UTC).isoformat(),
            "meta": meta or {},
            "instruction_shaped": bool(instruction_shaped),
        }
        try:
            with self._lock:
                directory = os.path.dirname(self.path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            return record["vault_id"]
        except Exception as exc:
            logger.error("Raw vault deposit failed: %s", exc)
            return None

    def fetch(self, vault_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve one raw record for audit/replay."""
        try:
            with self._lock, open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if record.get("vault_id") == vault_id:
                        return record
        except FileNotFoundError:
            return None
        except Exception as exc:
            logger.error("Raw vault fetch failed: %s", exc)
        return None

    def verify(self, vault_id: str) -> bool:
        """Re-hash a stored record's text and compare to its content_hash.

        Records predating the hash field cannot verify and return False.
        """
        record = self.fetch(vault_id)
        if record is None or "content_hash" not in record:
            return False
        return record["content_hash"] == _content_hash(record.get("text", ""))

    def all_records(self) -> List[Dict[str, Any]]:
        try:
            with self._lock, open(self.path, "r", encoding="utf-8") as handle:
                return [json.loads(line) for line in handle if line.strip()]
        except FileNotFoundError:
            return []
        except Exception as exc:
            logger.error("Raw vault read failed: %s", exc)
            return []

    def __len__(self) -> int:
        return len(self.all_records())


__all__ = ["RawVault", "default_vault_path"]
