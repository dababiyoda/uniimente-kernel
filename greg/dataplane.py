"""Untrusted data plane: web pages, emails, community replies, documents, model output.

External content is DATA. It is retained with provenance so it can inform
missions (community influence is real: signals are evidence a mission may read),
but it can never become a command: only an Ed25519-signed founder envelope in
the inbox is a command, and nothing here writes to the inbox or grants scope.

Instruction-shaped text is flagged and quarantined from any planner that would
otherwise quote it as guidance. The flag is a heuristic aid; the guarantee is
structural (the authority plane accepts only signed founder commands).
"""
from __future__ import annotations

import hashlib
import re

from greg.journal import Journal, iso, utcnow

INSTRUCTION_PATTERNS = [
    r"ignore (all |your |the )?(previous|prior|above) instructions",
    r"disregard (the |your )?(system|previous|prior)",
    r"you are now", r"new instructions?:", r"system prompt",
    r"(send|reveal|print|exfiltrate).{0,40}(secret|password|api key|token|credential|private key)",
    r"(grant|give|raise).{0,30}(permission|access|authority|budget)",
    r"run (this|the following) (command|code)", r"curl .*\|\s*(sh|bash)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INSTRUCTION_PATTERNS]
MAX_RETAINED = 8000


def instruction_shaped(text: str) -> list[str]:
    return [p.pattern for p in _COMPILED if p.search(text)]


def ingest(journal: Journal, *, source: str, content: str, channel: str) -> dict:
    """Retain one external item as inert evidence. Never a command, never authority."""
    if not isinstance(content, str):
        raise ValueError("external content must be text")
    flags = instruction_shaped(content)
    record = {"source": source[:500], "channel": channel[:100],
              "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
              "content": content[:MAX_RETAINED], "truncated": len(content) > MAX_RETAINED,
              "trust": "untrusted", "instruction_flags": flags, "quarantined": bool(flags),
              "may_command": False, "may_grant": False, "at": iso(utcnow())}
    journal.record("external.ingested", record, key=[source, record["content_sha256"]], sensitivity="confidential")
    return record


def community_signals(journal: Journal, channel: str) -> dict:
    """Aggregate non-quarantined community items into mission-readable evidence."""
    items = [e.payload for e in journal.replay("external.ingested") if e.payload["channel"] == channel]
    usable = [i for i in items if not i["quarantined"]]
    return {"channel": channel, "items": len(items), "usable": len(usable),
            "quarantined": len(items) - len(usable),
            "sources": sorted({i["source"] for i in usable})[:100]}
